"""Shell de proyectos (OZ-8): ventana única con vista central reemplazable (ADR-011).

La ventana es "tonta": toda la lógica de estado vive en `ShellViewModel` (testeado headless).
Aquí solo se conectan widgets a comandos del ViewModel y se pinta el estado que emite, y se
proveen las interacciones nativas —elegir archivo, confirmar descarte, mostrar error— que el
ViewModel pide por callback.

Accesibilidad (diseño §22): cada acción lleva atajo de teclado visible; el estado nunca se
comunica solo por color —un reciente roto se marca con ícono **y** texto—.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from application.project_service import ProjectService, ProjectState
from application.settings import SettingsRepository
from desktop.shell_viewmodel import DiscardChoice, ShellViewModel

DEFAULT_SIZE = (1024, 700)
PROJECT_FILTER = "Proyectos OpenZonda (*.wifisurvey)"
PROJECT_SUFFIX = ".wifisurvey"


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

        self._inicio = _InicioView(
            on_new=self._vm.request_new,
            on_open=lambda: self._vm.request_open(None),
            on_open_recent=lambda p: self._vm.request_open(p),
            on_remove_recent=self._vm.request_remove_recent,
        )
        self._proyecto = _ProyectoView(on_rename=self._vm.request_rename)
        self._stack = QStackedWidget(self)
        self._stack.addWidget(self._inicio)
        self._stack.addWidget(self._proyecto)
        self.setCentralWidget(self._stack)

        self._construir_acciones()
        self._vm.set_on_changed(self._al_cambiar_estado)

    # ------------------------------------------------------------------ construcción

    def _construir_acciones(self) -> None:
        estilo = self.style()
        barra = self.addToolBar("Proyecto")
        menu = self.menuBar().addMenu("&Archivo")

        def accion(texto: str, atajo: str, slot, icono=None, en_barra=False):
            act = menu.addAction(texto)
            act.setShortcut(atajo)
            act.triggered.connect(slot)
            if icono is not None:
                act.setIcon(estilo.standardIcon(icono))
            if en_barra:
                barra.addAction(act)
            return act

        accion(
            "&Nuevo",
            "Ctrl+N",
            self._vm.request_new,
            QStyle.StandardPixmap.SP_FileIcon,
            en_barra=True,
        )
        accion(
            "&Abrir…",
            "Ctrl+O",
            lambda: self._vm.request_open(None),
            QStyle.StandardPixmap.SP_DialogOpenButton,
            en_barra=True,
        )
        self._act_guardar = accion(
            "&Guardar",
            "Ctrl+S",
            self._vm.request_save,
            QStyle.StandardPixmap.SP_DialogSaveButton,
            en_barra=True,
        )
        self._act_guardar_como = accion("Guardar &como…", "Ctrl+Shift+S", self._vm.request_save_as)
        self._act_cerrar = accion("&Cerrar proyecto", "Ctrl+W", self._vm.request_close_project)
        self._menu_recientes = menu.addMenu("&Recientes")
        menu.addSeparator()
        accion("&Salir", "Ctrl+Q", self.close)

        self.statusBar().showMessage("Sin proyecto")

    # --------------------------------------------------------------- pintado de estado

    def _al_cambiar_estado(self, state: ProjectState) -> None:
        self.setWindowTitle(self._vm.window_title)
        self._act_guardar.setEnabled(state.has_project)
        self._act_guardar_como.setEnabled(state.has_project)
        self._act_cerrar.setEnabled(state.has_project)

        if state.has_project:
            self._stack.setCurrentWidget(self._proyecto)
            self._proyecto.mostrar(state)
            ruta = str(state.path) if state.path else "(sin guardar)"
            self.statusBar().showMessage(f"{state.name} — {ruta}")
        else:
            self._stack.setCurrentWidget(self._inicio)
            self.statusBar().showMessage("Sin proyecto")

        self._inicio.mostrar_recientes(state)
        self._poblar_menu_recientes(state)

    def _poblar_menu_recientes(self, state: ProjectState) -> None:
        self._menu_recientes.clear()
        if not state.recent:
            vacio = self._menu_recientes.addAction("(sin proyectos recientes)")
            vacio.setEnabled(False)
            return
        for entrada in state.recent:
            etiqueta = entrada.path.name
            if not entrada.available:
                etiqueta += "  (no disponible)"
            act = self._menu_recientes.addAction(etiqueta)
            act.setEnabled(entrada.available)
            act.setToolTip(str(entrada.path))
            act.triggered.connect(lambda _=False, p=entrada.path: self._vm.request_open(p))

    # --------------------------------------------------------- interacciones nativas

    def _pedir_ruta_abrir(self) -> Path | None:
        nombre, _ = QFileDialog.getOpenFileName(self, "Abrir proyecto", "", PROJECT_FILTER)
        return Path(nombre) if nombre else None

    def _pedir_ruta_guardar(self) -> Path | None:
        nombre, _ = QFileDialog.getSaveFileName(self, "Guardar proyecto como", "", PROJECT_FILTER)
        if not nombre:
            return None
        ruta = Path(nombre)
        if ruta.suffix != PROJECT_SUFFIX:
            ruta = ruta.with_suffix(PROJECT_SUFFIX)
        return ruta

    def _confirmar_descarte(self) -> DiscardChoice:
        caja = QMessageBox(self)
        caja.setIcon(QMessageBox.Icon.Warning)
        caja.setWindowTitle("Cambios sin guardar")
        caja.setText("El proyecto tiene cambios sin guardar.")
        caja.setInformativeText("¿Querés guardarlos antes de continuar?")
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
        titulo = QLabel("OpenZonda")
        titulo.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(titulo)

        botones = QHBoxLayout()
        nuevo = QPushButton("Nuevo proyecto")
        nuevo.clicked.connect(on_new)
        abrir = QPushButton("Abrir proyecto…")
        abrir.clicked.connect(on_open)
        botones.addWidget(nuevo)
        botones.addWidget(abrir)
        layout.addLayout(botones)

        layout.addWidget(QLabel("Recientes"))
        self._lista = QListWidget()
        self._lista.itemDoubleClicked.connect(self._abrir_item)
        layout.addWidget(self._lista, 1)

        self._quitar = QPushButton("Quitar de recientes")
        self._quitar.clicked.connect(self._quitar_seleccionado)
        layout.addWidget(self._quitar)

        self._vacio = QLabel("No hay proyectos recientes todavía.")
        self._vacio.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        layout.addWidget(self._vacio)

    def mostrar_recientes(self, state: ProjectState) -> None:
        self._lista.clear()
        estilo = self.style()
        for entrada in state.recent:
            texto = (
                entrada.path.name if entrada.available else f"{entrada.path.name}  —  no disponible"
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
    """Vista del proyecto abierto. En OZ-8 muestra identidad y nombre editable; el árbol de
    sitios/plantas y el plano llegan en tarjetas siguientes."""

    def __init__(self, *, on_rename) -> None:
        super().__init__()
        self._on_rename = on_rename
        form = QFormLayout(self)
        self._nombre = QLineEdit()
        # `textEdited` (no `editingFinished`) marca el cambio en el acto: si se usara
        # `editingFinished`, editar el nombre y cerrar con la X sin sacar el foco del campo
        # dejaría dirty en False y perdería la edición sin avisar (OZ-8, hallazgo del PO). Y
        # `textEdited` —a diferencia de `textChanged`— no se dispara con el `setText`
        # programático de `mostrar()`, así que poblar el campo no marca un dirty falso.
        self._nombre.textEdited.connect(lambda _texto: self._emitir_rename())
        self._ruta = QLabel()
        self._ruta.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addRow("Nombre", self._nombre)
        form.addRow("Archivo", self._ruta)

    def mostrar(self, state: ProjectState) -> None:
        if self._nombre.text() != (state.name or ""):
            self._nombre.setText(state.name or "")
        self._ruta.setText(str(state.path) if state.path else "(sin guardar)")

    def _emitir_rename(self) -> None:
        self._on_rename(self._nombre.text())
