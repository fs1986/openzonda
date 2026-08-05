"""Shell de proyectos (OZ-8): ventana única con vista central reemplazable (ADR-011).

La ventana es "tonta": toda la lógica de estado vive en `ShellViewModel` (testeado headless).
Aquí solo se conectan widgets a comandos del ViewModel y se pinta el estado que emite, y se
proveen las interacciones nativas —elegir archivo, confirmar descarte, mostrar error— que el
ViewModel pide por callback.

Accesibilidad (diseño §22): cada acción lleva atajo de teclado visible; el estado nunca se
comunica solo por color —un reciente roto se marca con ícono **y** texto—.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

from PySide6.QtCore import QT_TRANSLATE_NOOP, Qt
from PySide6.QtGui import QActionGroup, QPainter, QPixmap
from PySide6.QtWidgets import (
    QDockWidget,
    QFileDialog,
    QFormLayout,
    QGraphicsPixmapItem,
    QGraphicsScene,
    QGraphicsView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from application.project_service import ProjectService, ProjectState, ProjectStoreError
from application.settings import SettingsRepository
from desktop.floorplan_viewmodel import (
    FloorPlanViewModel,
    NewFloor,
    calibration_summary,
    plan_summary,
)
from desktop.shell_viewmodel import DiscardChoice, ShellViewModel
from desktop.visor_viewmodel import ActivePlan

DEFAULT_SIZE = (1024, 700)
# Filtros de diálogo: marcados para extracción (lupdate) en el contexto "MainWindow", que es
# donde se traducen con self.tr(). El sufijo no es texto de usuario y no se traduce.
PROJECT_FILTER = QT_TRANSLATE_NOOP("MainWindow", "Proyectos OpenZonda (*.wifisurvey)")
PROJECT_SUFFIX = ".wifisurvey"
IMAGE_FILTER = QT_TRANSLATE_NOOP("MainWindow", "Imágenes de plano (*.png *.jpg *.jpeg)")
_NODE_ROLE = Qt.ItemDataRole.UserRole


class MainWindow(QMainWindow):
    def __init__(
        self,
        project_service: ProjectService,
        settings_repository: SettingsRepository,
        app_version: str,
    ) -> None:
        super().__init__()
        self._settings_repository = settings_repository
        self._app_version = app_version
        self._restaurar_geometria()

        self._vm = ShellViewModel(
            project_service,
            ask_open_path=self._pedir_ruta_abrir,
            ask_save_path=self._pedir_ruta_guardar,
            confirm_discard=self._confirmar_descarte,
            show_error=self._mostrar_error,
        )

        self._tree_vm = FloorPlanViewModel(
            project_service,
            ask_site_name=self._pedir_nombre_sitio,
            ask_new_floor=self._pedir_nueva_planta,
            ask_rename=self._pedir_renombre,
            ask_image_path=self._pedir_imagen,
            confirm_remove=self._confirmar_eliminacion,
        )

        self._inicio = _InicioView(
            on_new=self._vm.request_new,
            on_open=lambda: self._vm.request_open(None),
            on_open_recent=lambda p: self._vm.request_open(p),
            on_remove_recent=self._vm.request_remove_recent,
        )
        self._proyecto = _ProyectoView(
            on_rename=self._vm.request_rename,
            on_calibrate=self._al_calibrar,
            on_rotate=self._al_rotar,
        )
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._inicio)
        self._stack.addWidget(self._proyecto)
        self.setCentralWidget(self._stack)

        # Disciplina de memoria: solo el pixmap de la planta activa vive (OZ-36). El release
        # es no-op porque reemplazar el item de la escena ya suelta el pixmap anterior; el
        # guardián garantiza además que no quede una segunda referencia colgada.
        self._service = project_service
        self._plano_activo: ActivePlan[QPixmap] = ActivePlan(self._cargar_pixmap, lambda _pm: None)
        self._floor_seleccionado: UUID | None = None

        self._arbol = _ArbolView(
            on_add_site=self._tree_vm.request_add_site,
            on_add_floor=self._tree_vm.request_add_floor,
            on_rename=self._al_renombrar_nodo,
            on_remove=self._al_eliminar_nodo,
            on_load_plan=self._tree_vm.request_load_plan,
            on_floor_selected=self._al_seleccionar_planta,
        )
        self._dock_arbol = QDockWidget(self.tr("Sitios y plantas"), self)
        self._dock_arbol.setObjectName("dockArbol")
        self._dock_arbol.setWidget(self._arbol)
        self.addDockWidget(Qt.DockWidgetArea.LeftDockWidgetArea, self._dock_arbol)

        self._construir_acciones()
        self._vm.set_on_changed(self._al_cambiar_estado)

    # ------------------------------------------------------------------ construcción

    def _construir_acciones(self) -> None:
        estilo = self.style()
        barra = self.addToolBar(self.tr("Proyecto"))
        menu = self.menuBar().addMenu(self.tr("&Archivo"))

        def accion(texto: str, atajo: str, slot, icono=None, en_barra=False):
            act = menu.addAction(texto)
            act.setShortcut(atajo)
            act.triggered.connect(slot)
            if icono is not None:
                act.setIcon(estilo.standardIcon(icono))
            if en_barra:
                barra.addAction(act)
            return act

        self._act_nuevo = accion(
            self.tr("&Nuevo"),
            "Ctrl+N",
            self._vm.request_new,
            QStyle.StandardPixmap.SP_FileIcon,
            en_barra=True,
        )
        self._act_abrir = accion(
            self.tr("&Abrir…"),
            "Ctrl+O",
            lambda: self._vm.request_open(None),
            QStyle.StandardPixmap.SP_DialogOpenButton,
            en_barra=True,
        )
        self._act_guardar = accion(
            self.tr("&Guardar"),
            "Ctrl+S",
            self._vm.request_save,
            QStyle.StandardPixmap.SP_DialogSaveButton,
            en_barra=True,
        )
        self._act_guardar_como = accion(
            self.tr("Guardar &como…"), "Ctrl+Shift+S", self._vm.request_save_as
        )
        self._act_cerrar = accion(
            self.tr("&Cerrar proyecto"), "Ctrl+W", self._vm.request_close_project
        )
        self._menu_recientes = menu.addMenu(self.tr("&Recientes"))
        self._construir_menu_idioma()
        menu.addSeparator()
        accion(self.tr("&Salir"), "Ctrl+Q", self.close)

        self.statusBar().showMessage(self.tr("Sin proyecto"))

    # --------------------------------------------------------------- pintado de estado

    def _al_cambiar_estado(self, state: ProjectState) -> None:
        self.setWindowTitle(self._vm.window_title)
        # Durante una operación de I/O (abrir/guardar en el worker, OZ-34) se deshabilitan las
        # acciones para no encolar trabajo mientras algo corre.
        ocupado = state.busy
        self._act_nuevo.setEnabled(not ocupado)
        self._act_abrir.setEnabled(not ocupado)
        self._act_guardar.setEnabled(state.has_project and not ocupado)
        self._act_guardar_como.setEnabled(state.has_project and not ocupado)
        self._act_cerrar.setEnabled(state.has_project and not ocupado)
        self._menu_recientes.setEnabled(not ocupado)

        if state.has_project:
            self._stack.setCurrentWidget(self._proyecto)
            self._proyecto.mostrar(state)
            self._dock_arbol.setVisible(True)
            self._arbol.setEnabled(not ocupado)
            if state.project is not None:
                self._arbol.mostrar(state.project)
        else:
            self._stack.setCurrentWidget(self._inicio)
            self._dock_arbol.setVisible(False)

        if ocupado:
            self.statusBar().showMessage(self.tr("Trabajando…"))
        elif state.has_project:
            ruta = str(state.path) if state.path else self.tr("(sin guardar)")
            self.statusBar().showMessage(f"{state.name} — {ruta}")
        else:
            self.statusBar().showMessage(self.tr("Sin proyecto"))

        self._inicio.mostrar_recientes(state)
        self._poblar_menu_recientes(state)

    def _poblar_menu_recientes(self, state: ProjectState) -> None:
        self._menu_recientes.clear()
        if not state.recent:
            vacio = self._menu_recientes.addAction(self.tr("(sin proyectos recientes)"))
            vacio.setEnabled(False)
            return
        for entrada in state.recent:
            etiqueta = entrada.path.name
            if not entrada.available:
                etiqueta += self.tr("  (no disponible)")
            act = self._menu_recientes.addAction(etiqueta)
            act.setEnabled(entrada.available)
            act.setToolTip(str(entrada.path))
            act.triggered.connect(lambda _=False, p=entrada.path: self._vm.request_open(p))

    # --------------------------------------------------------- interacciones nativas

    def _pedir_ruta_abrir(self) -> Path | None:
        nombre, _ = QFileDialog.getOpenFileName(
            self, self.tr("Abrir proyecto"), "", self.tr(PROJECT_FILTER)
        )
        return Path(nombre) if nombre else None

    def _pedir_ruta_guardar(self) -> Path | None:
        nombre, _ = QFileDialog.getSaveFileName(
            self, self.tr("Guardar proyecto como"), "", self.tr(PROJECT_FILTER)
        )
        if not nombre:
            return None
        ruta = Path(nombre)
        if ruta.suffix != PROJECT_SUFFIX:
            ruta = ruta.with_suffix(PROJECT_SUFFIX)
        return ruta

    def _confirmar_descarte(self) -> DiscardChoice:
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle(self.tr("Cambios sin guardar"))
        caja.setText(self.tr("El proyecto tiene cambios sin guardar."))
        caja.setInformativeText(self.tr("¿Querés guardarlos antes de continuar?"))
        caja.setStandardButtons(
            QMessageBox.StandardButton.Save
            | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel
        )
        caja.setDefaultButton(QMessageBox.StandardButton.Save)
        resultado = caja.exec()
        if resultado == QMessageBox.StandardButton.Save:
            return DiscardChoice.SAVE
        if resultado == QMessageBox.StandardButton.Discard:
            return DiscardChoice.DISCARD
        return DiscardChoice.CANCEL

    def _mostrar_error(self, titulo: str, mensaje: str) -> None:
        QMessageBox.critical(self, titulo, mensaje)

    # ----------------------------------------------- interacciones del árbol (OZ-9a)

    def _pedir_nombre_sitio(self) -> str | None:
        nombre, ok = QInputDialog.getText(
            self, self.tr("Nuevo sitio"), self.tr("Nombre del sitio:")
        )
        return nombre if ok and nombre.strip() else None

    def _pedir_renombre(self, actual: str) -> str | None:
        nombre, ok = QInputDialog.getText(
            self, self.tr("Renombrar"), self.tr("Nuevo nombre:"), text=actual
        )
        return nombre if ok and nombre.strip() else None

    def _pedir_imagen(self) -> Path | None:
        nombre, _ = QFileDialog.getOpenFileName(
            self, self.tr("Elegir plano"), "", self.tr(IMAGE_FILTER)
        )
        return Path(nombre) if nombre else None

    def _pedir_nueva_planta(self) -> NewFloor | None:
        """Recoge nombre, nivel e imagen de una planta nueva. Cancelar en cualquier paso
        aborta: el plano es obligatorio, así que no se crea una planta a medias (OZ-9a)."""
        nombre, ok = QInputDialog.getText(
            self, self.tr("Nueva planta"), self.tr("Nombre de la planta:")
        )
        if not ok or not nombre.strip():
            return None
        nivel, ok = QInputDialog.getInt(
            self, self.tr("Nueva planta"), self.tr("Nivel (0 = planta baja):"), 0
        )
        if not ok:
            return None
        imagen = self._pedir_imagen()
        if imagen is None:
            return None
        return NewFloor(name=nombre.strip(), level=nivel, image=imagen)

    def _confirmar_eliminacion(self, descripcion: str) -> bool:
        respuesta = QMessageBox.question(
            self,
            self.tr("Eliminar"),
            self.tr("¿Eliminar {que}? Esta acción no se puede deshacer.").format(que=descripcion),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        return respuesta == QMessageBox.StandardButton.Yes

    def _al_renombrar_nodo(self, kind: str, node_id: UUID, current: str) -> None:
        if kind == "site":
            self._tree_vm.request_rename_site(node_id, current)
        else:
            self._tree_vm.request_rename_floor(node_id, current)

    def _al_eliminar_nodo(self, kind: str, node_id: UUID, description: str) -> None:
        if kind == "site":
            self._tree_vm.request_remove_site(node_id, description)
        else:
            self._tree_vm.request_remove_floor(node_id, description)

    # ------------------------------------------------------ visor del plano (OZ-36)

    def _cargar_pixmap(self, sha: str) -> QPixmap:
        """Loader del `ActivePlan`: bytes del asset -> `QPixmap`. Solo se llama al cambiar de
        planta (mismo sha no recarga), así que aquí es donde se decodifica el plano."""
        pixmap = QPixmap()
        pixmap.loadFromData(self._service.read_asset_by_sha(sha))
        return pixmap

    def _floor_por_id(self, floor_id: UUID | None):
        proyecto = self._vm.state.project
        if floor_id is None or proyecto is None:
            return None
        for site in proyecto.sites:
            for floor in site.floors:
                if floor.id == floor_id:
                    return floor
        return None

    def _al_seleccionar_planta(self, floor_id: UUID | None) -> None:
        self._floor_seleccionado = floor_id
        floor = self._floor_por_id(floor_id)
        if floor is None:
            self._plano_activo.clear()
            self._proyecto.limpiar_plano()
            return
        try:
            self._plano_activo.set(floor.plan.asset_sha256)
        except ProjectStoreError as e:
            self._plano_activo.clear()
            self._proyecto.limpiar_plano()
            self._mostrar_error(self.tr("No se pudo cargar el plano"), e.message)
            return
        self._proyecto.mostrar_plano(
            self._plano_activo.resource,
            floor.plan.rotation_degrees,
            calibration_summary(floor.plan),
        )

    def _al_calibrar(self, first: tuple[float, float], second: tuple[float, float]) -> None:
        """Recibe los dos puntos (en píxeles de imagen) que el visor capturó; pide la distancia
        real y persiste la calibración. El error de escala lo calcula el dominio."""
        if self._floor_seleccionado is None:
            return
        metros, ok = QInputDialog.getDouble(
            self,
            self.tr("Calibrar"),
            self.tr("Distancia real entre los dos puntos (metros):"),
            1.0,
            0.001,
            100000.0,
            3,
        )
        if not ok:
            return
        self._service.set_floor_calibration(self._floor_seleccionado, first, second, metros)

    def _al_rotar(self) -> None:
        floor = self._floor_por_id(self._floor_seleccionado)
        if floor is not None:
            self._service.set_floor_rotation(floor.id, (floor.plan.rotation_degrees + 90.0) % 360.0)

    # ------------------------------------------------------------------- idioma (OZ-35)

    def _construir_menu_idioma(self) -> None:
        """Menú para elegir el idioma. Persiste la preferencia; aplica al reiniciar (ADR-013)."""
        menu = self.menuBar().addMenu(self.tr("&Idioma"))
        actual = self._settings_repository.load().language
        opciones = (
            (self.tr("Automático (sistema)"), "system"),
            (self.tr("Español"), "es"),
            (self.tr("English"), "en"),
        )
        grupo = QActionGroup(self)
        grupo.setExclusive(True)
        for etiqueta, codigo in opciones:
            act = menu.addAction(etiqueta)
            act.setCheckable(True)
            act.setChecked(codigo == actual)
            act.triggered.connect(lambda _=False, c=codigo: self._elegir_idioma(c))
            grupo.addAction(act)

    def _elegir_idioma(self, codigo: str) -> None:
        settings = self._settings_repository.load()
        if settings.language == codigo:
            return
        self._settings_repository.save(settings.with_changes(language=codigo))
        QMessageBox.information(
            self,
            self.tr("Idioma"),
            self.tr("El idioma se aplicará la próxima vez que abras OpenZonda."),
        )

    # ---------------------------------------------------------------------- geometría

    def _restaurar_geometria(self) -> None:
        geometria = self._settings_repository.load().window_geometry
        if geometria is None:
            self.resize(*DEFAULT_SIZE)
            return
        x, y, ancho, alto = geometria
        self.setGeometry(x, y, ancho, alto)

    def closeEvent(self, event) -> None:
        if not self._vm.can_close_window():
            event.ignore()
            return
        # Relee antes de guardar: el servicio persiste recientes por su lado con el mismo
        # patrón, y así la geometría no pisa ese campo (settings.save reemplaza todo).
        settings = self._settings_repository.load()
        rect = self.geometry()
        self._settings_repository.save(
            settings.with_changes(window_geometry=(rect.x(), rect.y(), rect.width(), rect.height()))
        )
        super().closeEvent(event)


class _InicioView(QWidget):
    """Pantalla de inicio: crear, abrir y recientes, con estado vacío."""

    def __init__(self, *, on_new, on_open, on_open_recent, on_remove_recent) -> None:
        super().__init__()
        self._on_open_recent = on_open_recent
        self._on_remove_recent = on_remove_recent

        layout = QVBoxLayout(self)
        titulo = QLabel("OpenZonda")  # marca: no se traduce
        titulo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(titulo)

        botones = QHBoxLayout()
        nuevo = QPushButton(self.tr("Nuevo proyecto"))
        nuevo.clicked.connect(on_new)
        abrir = QPushButton(self.tr("Abrir proyecto…"))
        abrir.clicked.connect(on_open)
        botones.addWidget(nuevo)
        botones.addWidget(abrir)
        layout.addLayout(botones)

        layout.addWidget(QLabel(self.tr("Recientes")))
        self._lista = QListWidget()
        self._lista.itemDoubleClicked.connect(self._abrir_item)
        layout.addWidget(self._lista, 1)

        self._quitar = QPushButton(self.tr("Quitar de recientes"))
        self._quitar.clicked.connect(self._quitar_seleccionado)
        layout.addWidget(self._quitar)

        self._vacio = QLabel(self.tr("No hay proyectos recientes todavía."))
        self._vacio.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._vacio)

    def mostrar_recientes(self, state: ProjectState) -> None:
        self._lista.clear()
        estilo = self.style()
        for entrada in state.recent:
            texto = (
                entrada.path.name
                if entrada.available
                else self.tr("{nombre}  —  no disponible").format(nombre=entrada.path.name)
            )
            item = QListWidgetItem(texto)
            item.setData(Qt.ItemDataRole.UserRole, str(entrada.path))
            item.setToolTip(str(entrada.path))
            if not entrada.available:
                # Doble canal: además del texto "no disponible", un ícono de advertencia.
                item.setIcon(estilo.standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning))
            self._lista.addItem(item)
        hay = bool(state.recent)
        self._lista.setVisible(hay)
        self._quitar.setVisible(hay)
        self._vacio.setVisible(not hay)

    def _abrir_item(self, item: QListWidgetItem) -> None:
        ruta = Path(item.data(Qt.ItemDataRole.UserRole))
        self._on_open_recent(ruta)

    def _quitar_seleccionado(self) -> None:
        item = self._lista.currentItem()
        if item is not None:
            self._on_remove_recent(Path(item.data(Qt.ItemDataRole.UserRole)))


class _ProyectoView(QWidget):
    """Vista central del proyecto: identidad editable arriba y el visor del plano abajo. El
    árbol Site→Floor vive en el dock lateral (`_ArbolView`)."""

    def __init__(self, *, on_rename, on_calibrate, on_rotate) -> None:
        super().__init__()
        self._on_rename = on_rename

        layout = QVBoxLayout(self)
        form = QFormLayout()
        self._nombre = QLineEdit()
        # `textEdited` (no `editingFinished`) marca el cambio en el acto: si se usara
        # `editingFinished`, editar el nombre y cerrar con la X sin sacar el foco del campo
        # dejaría dirty en False y perdería la edición sin avisar (OZ-8, hallazgo del PO). Y
        # `textEdited` —a diferencia de `textChanged`— no se dispara con el `setText`
        # programático de `mostrar()`, así que poblar el campo no marca un dirty falso.
        self._nombre.textEdited.connect(lambda _texto: self._emitir_rename())
        self._ruta = QLabel()
        self._ruta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow(self.tr("Nombre"), self._nombre)
        form.addRow(self.tr("Archivo"), self._ruta)
        layout.addLayout(form)

        self._visor = _VisorPanel(on_calibrate=on_calibrate, on_rotate=on_rotate)
        layout.addWidget(self._visor, 1)

    def mostrar(self, state: ProjectState) -> None:
        if self._nombre.text() != (state.name or ""):
            self._nombre.setText(state.name or "")
        self._ruta.setText(str(state.path) if state.path else self.tr("(sin guardar)"))

    def mostrar_plano(self, pixmap: QPixmap | None, rotation: float, calib_text: str) -> None:
        self._visor.mostrar_plano(pixmap, rotation, calib_text)

    def limpiar_plano(self) -> None:
        self._visor.limpiar()

    def _emitir_rename(self) -> None:
        self._on_rename(self._nombre.text())


class _ArbolView(QWidget):
    """Dock del árbol Site→Floor + resumen textual del plano de la planta seleccionada.

    OZ-9a NO renderiza el plano (eso es el visor de OZ-36): muestra el árbol y, para la planta
    elegida, un resumen con dimensiones y DPI acompañado de su procedencia en texto —"del
    archivo" vs. "asumido"—. Ese resumen es lo que hace validable la honestidad del plano sin
    depender del visor, y cumple el doble canal de accesibilidad (nunca solo color).
    """

    def __init__(
        self, *, on_add_site, on_add_floor, on_rename, on_remove, on_load_plan, on_floor_selected
    ) -> None:
        super().__init__()
        self._on_add_site = on_add_site
        self._on_add_floor = on_add_floor
        self._on_rename = on_rename
        self._on_remove = on_remove
        self._on_load_plan = on_load_plan
        self._on_floor_selected = on_floor_selected

        layout = QVBoxLayout(self)
        self._tree = QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setColumnCount(1)
        self._tree.currentItemChanged.connect(lambda *_: self._al_cambiar_seleccion())
        layout.addWidget(self._tree, 1)

        botones = QHBoxLayout()
        self._btn_sitio = QPushButton(self.tr("+ Sitio"))
        self._btn_sitio.clicked.connect(lambda: self._on_add_site())
        self._btn_planta = QPushButton(self.tr("+ Planta"))
        self._btn_planta.clicked.connect(self._agregar_planta)
        self._btn_plano = QPushButton(self.tr("Cargar plano…"))
        self._btn_plano.clicked.connect(self._cargar_plano)
        self._btn_renombrar = QPushButton(self.tr("Renombrar…"))
        self._btn_renombrar.clicked.connect(self._renombrar)
        self._btn_eliminar = QPushButton(self.tr("Eliminar"))
        self._btn_eliminar.clicked.connect(self._eliminar)
        for b in (
            self._btn_sitio,
            self._btn_planta,
            self._btn_plano,
            self._btn_renombrar,
            self._btn_eliminar,
        ):
            botones.addWidget(b)
        layout.addLayout(botones)

        self._resumen = QLabel(self.tr("Seleccioná una planta para ver su plano."))
        self._resumen.setWordWrap(True)
        self._resumen.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._resumen)

        self._actualizar_botones()

    # -------------------------------------------------------------------- pintado

    def mostrar(self, project) -> None:
        seleccion = self._id_seleccionado()
        self._tree.blockSignals(True)
        self._tree.clear()
        for site in project.sites:
            s_item = QTreeWidgetItem([site.name])
            s_item.setData(0, _NODE_ROLE, {"kind": "site", "id": str(site.id)})
            for floor in site.floors:
                f_item = QTreeWidgetItem(
                    [
                        self.tr("{nombre}  ·  nivel {nivel}").format(
                            nombre=floor.name, nivel=floor.level
                        )
                    ]
                )
                f_item.setData(
                    0,
                    _NODE_ROLE,
                    {
                        "kind": "floor",
                        "id": str(floor.id),
                        "name": floor.name,
                        "summary": plan_summary(floor.plan),
                    },
                )
                s_item.addChild(f_item)
            self._tree.addTopLevelItem(s_item)
        self._tree.expandAll()
        self._tree.blockSignals(False)
        self._reseleccionar(seleccion)
        self._al_cambiar_seleccion()

    # ------------------------------------------------------------------- acciones

    def _agregar_planta(self) -> None:
        datos = self._nodo_actual()
        if datos is None:
            return
        # Agregar planta cuelga del sitio: si hay una planta seleccionada, se usa su sitio padre.
        site_id = datos["id"] if datos["kind"] == "site" else self._site_padre()
        if site_id is not None:
            self._on_add_floor(UUID(site_id))

    def _cargar_plano(self) -> None:
        datos = self._nodo_actual()
        if datos is not None and datos["kind"] == "floor":
            self._on_load_plan(UUID(datos["id"]))

    def _renombrar(self) -> None:
        datos = self._nodo_actual()
        if datos is None:
            return
        actual = self._tree.currentItem().text(0) if datos["kind"] == "site" else datos["name"]
        self._on_rename(datos["kind"], UUID(datos["id"]), actual)

    def _eliminar(self) -> None:
        datos = self._nodo_actual()
        if datos is None:
            return
        que = self.tr("el sitio") if datos["kind"] == "site" else self.tr("la planta")
        self._on_remove(datos["kind"], UUID(datos["id"]), que)

    # -------------------------------------------------------------------- internos

    def _al_cambiar_seleccion(self) -> None:
        datos = self._nodo_actual()
        es_planta = datos is not None and datos["kind"] == "floor"
        if es_planta:
            self._resumen.setText(self.tr("Plano: {resumen}").format(resumen=datos["summary"]))
        else:
            self._resumen.setText(self.tr("Seleccioná una planta para ver su plano."))
        self._actualizar_botones()
        self._on_floor_selected(UUID(datos["id"]) if es_planta else None)

    def _actualizar_botones(self) -> None:
        datos = self._nodo_actual()
        hay = datos is not None
        es_planta = hay and datos["kind"] == "floor"
        # Agregar planta requiere un sitio (directo o el padre de la planta seleccionada).
        self._btn_planta.setEnabled(hay)
        self._btn_plano.setEnabled(es_planta)
        self._btn_renombrar.setEnabled(hay)
        self._btn_eliminar.setEnabled(hay)

    def _nodo_actual(self) -> dict | None:
        item = self._tree.currentItem()
        return item.data(0, _NODE_ROLE) if item is not None else None

    def _site_padre(self) -> str | None:
        item = self._tree.currentItem()
        padre = item.parent() if item is not None else None
        if padre is None:
            return None
        datos = padre.data(0, _NODE_ROLE)
        return datos["id"] if datos else None

    def _id_seleccionado(self) -> str | None:
        datos = self._nodo_actual()
        return datos["id"] if datos else None

    def _reseleccionar(self, node_id: str | None) -> None:
        if node_id is None:
            return
        for item in self._recorrer():
            datos = item.data(0, _NODE_ROLE)
            if datos and datos["id"] == node_id:
                self._tree.setCurrentItem(item)
                return

    def _recorrer(self) -> Iterator[QTreeWidgetItem]:
        for i in range(self._tree.topLevelItemCount()):
            site = self._tree.topLevelItem(i)
            if site is None:  # pragma: no cover - el rango garantiza no-nulo
                continue
            yield site
            for j in range(site.childCount()):
                hijo = site.child(j)
                if hijo is not None:  # pragma: no cover
                    yield hijo


class _Lienzo(QGraphicsView):
    """`QGraphicsView` del plano. La escena está en **píxeles de imagen**: el pixmap va en el
    origen sin escalar ni rotar, así que zoom, pan y rotación viven en la transformación de la
    *vista* y `mapToScene` los invierte. Por eso los dos puntos de calibración se capturan en
    coordenadas de imagen, invariantes al zoom con que el usuario los marcó (OZ-36).
    """

    def __init__(self, on_two_points) -> None:
        super().__init__()
        self._on_two_points = on_two_points
        self._escena = QGraphicsScene(self)
        self.setScene(self._escena)
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)  # pan con arrastre
        self.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, True)
        self._rotacion = 0.0
        self._calibrando = False
        self._puntos: list[tuple[float, float]] = []

    def mostrar(self, pixmap: QPixmap, rotation: float) -> None:
        self._escena.clear()
        item = QGraphicsPixmapItem(pixmap)
        self._escena.addItem(item)
        self._escena.setSceneRect(item.boundingRect())  # escena = píxeles de imagen
        self._rotacion = rotation
        self.ajustar()

    def limpiar(self) -> None:
        self._escena.clear()
        self._cancelar_calibracion()

    def ajustar(self) -> None:
        """Fit-to-view: encuadra el plano respetando la rotación persistente. No se persiste."""
        self.resetTransform()
        self.rotate(self._rotacion)
        if not self._escena.sceneRect().isEmpty():
            self.fitInView(self._escena.sceneRect(), Qt.AspectRatioMode.KeepAspectRatio)

    def wheelEvent(self, event) -> None:  # zoom, solo viewport (no se persiste)
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.scale(factor, factor)

    def iniciar_calibracion(self) -> None:
        self._calibrando = True
        self._puntos = []
        self.setDragMode(QGraphicsView.DragMode.NoDrag)  # los clics marcan puntos, no pan
        self.setCursor(Qt.CursorShape.CrossCursor)

    def _cancelar_calibracion(self) -> None:
        self._calibrando = False
        self._puntos = []
        self.setDragMode(QGraphicsView.DragMode.ScrollHandDrag)
        self.unsetCursor()

    def mousePressEvent(self, event) -> None:
        if not self._calibrando or event.button() != Qt.MouseButton.LeftButton:
            super().mousePressEvent(event)
            return
        p = self.mapToScene(event.position().toPoint())  # -> píxeles de imagen
        self._puntos.append((p.x(), p.y()))
        if len(self._puntos) == 2:
            primero, segundo = self._puntos
            self._cancelar_calibracion()
            self._on_two_points(primero, segundo)


class _VisorPanel(QWidget):
    """Panel del visor: el lienzo del plano + acciones (ajustar, rotar, calibrar) + el resumen
    de escala e incertidumbre **siempre visible** (OZ-36). No renderiza survey ni heatmap."""

    def __init__(self, *, on_calibrate, on_rotate) -> None:
        super().__init__()
        self._on_calibrate = on_calibrate
        self._on_rotate = on_rotate

        layout = QVBoxLayout(self)
        self._lienzo = _Lienzo(on_two_points=self._al_capturar_puntos)
        layout.addWidget(self._lienzo, 1)

        acciones = QHBoxLayout()
        self._btn_ajustar = QPushButton(self.tr("Ajustar"))
        self._btn_ajustar.clicked.connect(self._lienzo.ajustar)
        self._btn_rotar = QPushButton(self.tr("Rotar 90°"))
        self._btn_rotar.clicked.connect(lambda: self._on_rotate())
        self._btn_calibrar = QPushButton(self.tr("Calibrar…"))
        self._btn_calibrar.clicked.connect(self._lienzo.iniciar_calibracion)
        for b in (self._btn_ajustar, self._btn_rotar, self._btn_calibrar):
            acciones.addWidget(b)
        acciones.addStretch(1)
        layout.addLayout(acciones)

        # Escala + incertidumbre: siempre visible, en texto (doble canal). Nunca solo cuando
        # el error es alto (ADR-006).
        self._escala = QLabel(self.tr("Sin planta seleccionada."))
        self._escala.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self._escala)

        self._habilitar(False)

    def mostrar_plano(self, pixmap: QPixmap | None, rotation: float, calib_text: str) -> None:
        if pixmap is None or pixmap.isNull():
            self.limpiar()
            return
        self._lienzo.mostrar(pixmap, rotation)
        self._escala.setText(calib_text)
        self._habilitar(True)

    def limpiar(self) -> None:
        self._lienzo.limpiar()
        self._escala.setText(self.tr("Sin planta seleccionada."))
        self._habilitar(False)

    def _al_capturar_puntos(self, first: tuple[float, float], second: tuple[float, float]) -> None:
        self._on_calibrate(first, second)

    def _habilitar(self, activo: bool) -> None:
        self._btn_ajustar.setEnabled(activo)
        self._btn_rotar.setEnabled(activo)
        self._btn_calibrar.setEnabled(activo)
