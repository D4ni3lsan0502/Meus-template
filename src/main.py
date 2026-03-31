import sys
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QVBoxLayout, QLabel, QFrame, QMenuBar, QMenu, QFileDialog, QMessageBox,
    QDockWidget, QPushButton, QDoubleSpinBox, QHBoxLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from src.dicom_reader import read_dicom_series, sitk_to_vtk, DicomReaderError
from src.mpr_manager import MPRManager
from src.volume_renderer import VolumeRenderer
from src.mesh_manager import MeshManager, MeshManagerError
from src.registration_manager import RegistrationManager, RegistrationManagerError
from src.nerve_manager import NerveManager
from src.implant_manager import ImplantManager

class VtkViewport(QWidget):
    """
    Um widget customizado que contém uma janela de renderização do VTK
    e um label identificando o plano (Axial, Sagittal, Coronal ou 3D).
    """
    def __init__(self, title, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Label de título
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("background-color: #333; color: white; padding: 2px;")
        self.layout.addWidget(self.title_label)

        # Interactor VTK (QVTKRenderWindowInteractor)
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        self.layout.addWidget(self.vtkWidget)

        # Configurar Renderer do VTK
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(0.1, 0.1, 0.1) # Cor de fundo escura (cinza escuro)
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)

        # Interactor Style para imagens 2D ou 3D
        if title == "3D View":
            style = vtk.vtkInteractorStyleTrackballCamera()
        else:
            style = vtk.vtkInteractorStyleImage()

        self.vtkWidget.GetRenderWindow().GetInteractor().SetInteractorStyle(style)

        # Para testes visuais, adicionar um cubo 3D no viewport 3D e nos 2D
        # Na Fase 2 isso será substituído pelos dados DICOM/STL
        source = vtk.vtkCubeSource()
        source.SetCenter(0, 0, 0)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(source.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)

        # Cor do cubo dependendo da View para debug visual
        if title == "Axial":
            actor.GetProperty().SetColor(1.0, 0.0, 0.0) # Vermelho
        elif title == "Sagittal":
            actor.GetProperty().SetColor(0.0, 1.0, 0.0) # Verde
        elif title == "Coronal":
            actor.GetProperty().SetColor(0.0, 0.0, 1.0) # Azul
        else:
            actor.GetProperty().SetColor(1.0, 1.0, 0.0) # Amarelo (3D)

        self.renderer.AddActor(actor)
        self.renderer.ResetCamera()

    def start(self):
        """Inicializa a janela VTK."""
        self.vtkWidget.Initialize()
        self.vtkWidget.Start()


class MainWindow(QMainWindow):
    """
    Janela Principal do Software de Planejamento de Implantes.
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Implant Planner - Fase 2 (Leitura DICOM)")
        self.resize(1024, 768)

        # Criar a barra de menu
        self.create_menu_bar()

        # Widget Central
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Layout Grid (2x2 para os 4 viewports)
        grid_layout = QGridLayout(central_widget)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(5)

        # Criar os 4 viewports
        self.view_axial = VtkViewport("Axial")
        self.view_sagittal = VtkViewport("Sagittal")
        self.view_coronal = VtkViewport("Coronal")
        self.view_3d = VtkViewport("3D View")

        # Adicionar ao Grid
        # 0,0 (Topo-Esquerda): Axial
        # 0,1 (Topo-Direita): 3D View
        # 1,0 (Base-Esquerda): Coronal
        # 1,1 (Base-Direita): Sagittal
        grid_layout.addWidget(self.view_axial, 0, 0)
        grid_layout.addWidget(self.view_3d, 0, 1)
        grid_layout.addWidget(self.view_coronal, 1, 0)
        grid_layout.addWidget(self.view_sagittal, 1, 1)

        # Inicializa o MPR Manager
        self.mpr_manager = MPRManager(
            interactor_axial=self.view_axial.vtkWidget,
            interactor_coronal=self.view_coronal.vtkWidget,
            interactor_sagittal=self.view_sagittal.vtkWidget
        )

        # Inicializa o Volume Renderer (Crânio/Mandíbula 3D)
        self.volume_renderer = VolumeRenderer(
            interactor=self.view_3d.vtkWidget
        )

        # Inicializa o Gerenciador de Malhas (Escaneamento Intraoral)
        # O MeshManager compartilha do mesmo renderer e render_window do VolumeRenderer (4º Quadrante)
        self.mesh_manager = MeshManager(
            renderer=self.volume_renderer.renderer,
            render_window=self.volume_renderer.render_window
        )

        # Inicializa o Gerenciador de Registro (Landmark + ICP)
        self.registration_manager = RegistrationManager(
            interactor=self.view_3d.vtkWidget,
            renderer=self.volume_renderer.renderer,
            render_window=self.volume_renderer.render_window
        )

        # Inicializa o Gerenciador de Nervo Mandibular
        self.nerve_manager = NerveManager(
            interactors=[
                self.view_axial.vtkWidget,
                self.view_coronal.vtkWidget,
                self.view_sagittal.vtkWidget,
                self.view_3d.vtkWidget
            ],
            renderers=[
                self.mpr_manager.viewers[2].GetRenderer(), # Axial
                self.mpr_manager.viewers[1].GetRenderer(), # Coronal
                self.mpr_manager.viewers[0].GetRenderer(), # Sagital
                self.volume_renderer.renderer
            ],
            render_windows=[
                self.view_axial.vtkWidget.GetRenderWindow(),
                self.view_coronal.vtkWidget.GetRenderWindow(),
                self.view_sagittal.vtkWidget.GetRenderWindow(),
                self.view_3d.vtkWidget.GetRenderWindow()
            ]
        )

        # Inicializa o Gerenciador de Implantes (Fase 8)
        self.implant_manager = ImplantManager(
            interactors=[
                self.view_axial.vtkWidget,
                self.view_coronal.vtkWidget,
                self.view_sagittal.vtkWidget,
                self.view_3d.vtkWidget
            ],
            renderers=[
                self.mpr_manager.viewers[2].GetRenderer(), # Axial
                self.mpr_manager.viewers[1].GetRenderer(), # Coronal
                self.mpr_manager.viewers[0].GetRenderer(), # Sagital
                self.volume_renderer.renderer
            ],
            render_windows=[
                self.view_axial.vtkWidget.GetRenderWindow(),
                self.view_coronal.vtkWidget.GetRenderWindow(),
                self.view_sagittal.vtkWidget.GetRenderWindow(),
                self.view_3d.vtkWidget.GetRenderWindow()
            ]
        )

        # Criar o Painel de Ferramentas (Dock Widget)
        self.create_tools_dock()
        self.create_implant_dock()

    def create_implant_dock(self):
        """Cria um painel lateral esquerdo contendo os controles de Implante Virtual (Fase 8)."""
        dock = QDockWidget("Gerenciador de Implantes", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop)

        # Botão principal
        btn_add = QPushButton("Adicionar Implante")
        btn_add.clicked.connect(self.on_add_implant)

        # Controles Paramétricos (Comprimento e Diâmetro)
        # O padrão do mercado é 4.0mm de diâmetro e 10mm de comprimento
        lbl_size = QLabel("<b>Dimensões (mm):</b>")

        h_layout_d = QHBoxLayout()
        h_layout_d.addWidget(QLabel("Diâmetro:"))
        self.spin_diameter = QDoubleSpinBox()
        self.spin_diameter.setRange(2.0, 8.0)
        self.spin_diameter.setSingleStep(0.5)
        self.spin_diameter.setValue(4.0)
        self.spin_diameter.valueChanged.connect(self.on_implant_parameter_changed)
        h_layout_d.addWidget(self.spin_diameter)

        h_layout_l = QHBoxLayout()
        h_layout_l.addWidget(QLabel("Comprimento:"))
        self.spin_length = QDoubleSpinBox()
        self.spin_length.setRange(5.0, 20.0)
        self.spin_length.setSingleStep(1.0)
        self.spin_length.setValue(10.0)
        self.spin_length.valueChanged.connect(self.on_implant_parameter_changed)
        h_layout_l.addWidget(self.spin_length)

        # Controles de Angulação
        lbl_angle = QLabel("<br><b>Angulação (Graus):</b>")

        h_layout_tilt = QHBoxLayout()
        h_layout_tilt.addWidget(QLabel("Tilt (X):"))
        self.spin_tilt = QDoubleSpinBox()
        self.spin_tilt.setRange(-90.0, 90.0)
        self.spin_tilt.setSingleStep(5.0)
        self.spin_tilt.setValue(0.0)
        self.spin_tilt.valueChanged.connect(self.on_implant_parameter_changed)
        h_layout_tilt.addWidget(self.spin_tilt)

        h_layout_pan = QHBoxLayout()
        h_layout_pan.addWidget(QLabel("Pan (Y):"))
        self.spin_pan = QDoubleSpinBox()
        self.spin_pan.setRange(-90.0, 90.0)
        self.spin_pan.setSingleStep(5.0)
        self.spin_pan.setValue(0.0)
        self.spin_pan.valueChanged.connect(self.on_implant_parameter_changed)
        h_layout_pan.addWidget(self.spin_pan)

        # Adicionar os blocos na UI
        layout.addWidget(btn_add)
        layout.addWidget(lbl_size)
        layout.addLayout(h_layout_d)
        layout.addLayout(h_layout_l)
        layout.addWidget(lbl_angle)
        layout.addLayout(h_layout_tilt)
        layout.addLayout(h_layout_pan)

        dock.setWidget(panel)
        self.addDockWidget(Qt.LeftDockWidgetArea, dock)

    def create_tools_dock(self):
        """Cria um painel lateral contendo os controles da Fase 6 (Registro/ICP)."""
        dock = QDockWidget("Registration Tools", self)
        dock.setAllowedAreas(Qt.LeftDockWidgetArea | Qt.RightDockWidgetArea)

        # Container e Layout
        panel = QWidget()
        layout = QVBoxLayout(panel)
        layout.setAlignment(Qt.AlignTop)

        # Etapa 1: Landmarks (Coarse Fit)
        lbl_step1 = QLabel("<b>Step 1: Landmark Registration</b>")
        btn_mark_dicom = QPushButton("Marcar Pontos DICOM")
        btn_mark_dicom.clicked.connect(self.on_mark_dicom_points)

        btn_mark_mesh = QPushButton("Marcar Pontos STL")
        btn_mark_mesh.clicked.connect(self.on_mark_mesh_points)

        btn_align = QPushButton("Alinhar por Pontos (Coarse)")
        btn_align.clicked.connect(self.on_align_landmarks)

        # Etapa 2: ICP (Fine Fit)
        lbl_step2 = QLabel("<br><b>Step 2: Auto Refinement</b>")
        btn_icp = QPushButton("Refinar (ICP)")
        btn_icp.clicked.connect(self.on_refine_icp)

        # Etapa 3: Mapeamento do Canal Mandibular (Nervo)
        lbl_step3 = QLabel("<br><b>Step 3: Nerve Mapping</b>")
        btn_start_nerve = QPushButton("Iniciar Mapeamento de Nervo")
        btn_start_nerve.clicked.connect(self.on_start_nerve_mapping)

        btn_undo_nerve = QPushButton("Desfazer Último Ponto")
        btn_undo_nerve.clicked.connect(self.on_undo_nerve_point)

        btn_finish_nerve = QPushButton("Finalizar Nervo")
        btn_finish_nerve.clicked.connect(self.on_finish_nerve_mapping)

        # Adiciona botões ao painel
        layout.addWidget(lbl_step1)
        layout.addWidget(btn_mark_dicom)
        layout.addWidget(btn_mark_mesh)
        layout.addWidget(btn_align)
        layout.addWidget(lbl_step2)
        layout.addWidget(btn_icp)
        layout.addWidget(lbl_step3)
        layout.addWidget(btn_start_nerve)
        layout.addWidget(btn_undo_nerve)
        layout.addWidget(btn_finish_nerve)

        dock.setWidget(panel)
        self.addDockWidget(Qt.RightDockWidgetArea, dock)

    def create_menu_bar(self):
        """Cria o menu superior da janela principal."""
        menu_bar = self.menuBar()

        # Menu Arquivo (File)
        file_menu = menu_bar.addMenu("File")

        # Ação Importar DICOM
        import_dicom_action = QAction("Import DICOM Folder", self)
        import_dicom_action.setStatusTip("Import a folder containing DICOM series")
        import_dicom_action.triggered.connect(self.import_dicom_folder)
        file_menu.addAction(import_dicom_action)

        # Ação Importar Malha Intraoral
        import_mesh_action = QAction("Import Intraoral Scan", self)
        import_mesh_action.setStatusTip("Import STL, PLY or OBJ intraoral surface mesh")
        import_mesh_action.triggered.connect(self.import_intraoral_scan)
        file_menu.addAction(import_mesh_action)

    def import_dicom_folder(self):
        """Abre uma caixa de diálogo para o usuário escolher a pasta DICOM e inicia a importação."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Select DICOM Folder",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )

        if dir_path:
            try:
                # Usa o módulo dicom_reader para ler o volume via SimpleITK
                sitk_image = read_dicom_series(dir_path)

                # Converte para vtkImageData (conforme Fase 2, impressão de resultados já ocorre nas funções)
                vtk_data = sitk_to_vtk(sitk_image)

                # Renderizar MPR via MPR Manager
                self.mpr_manager.set_volume(vtk_data)

                # Renderizar Crânio/Mandíbula 3D na GPU
                self.volume_renderer.set_volume(vtk_data)

                # Passa o volume para o Gerenciador de Registro também
                self.registration_manager.set_dicom_volume(vtk_data)

                # Log de sucesso
                print("Leitura e conversão DICOM completadas com sucesso!")
                QMessageBox.information(
                    self,
                    "DICOM Importado",
                    f"Série importada com sucesso e MPR/Volume 3D renderizados.\n"
                    f"Dimensões VTK: {vtk_data.GetDimensions()}\n"
                    f"Espaçamento VTK: {vtk_data.GetSpacing()}"
                )

                # Guarda os dados carregados no estado do software
                self.current_vtk_volume = vtk_data

            except DicomReaderError as e:
                QMessageBox.critical(self, "Erro DICOM", str(e))
                print(f"Erro ao carregar DICOM: {str(e)}")
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro fatal: {str(e)}")

    def import_intraoral_scan(self):
        """Abre uma caixa de diálogo para o usuário escolher a malha 3D e renderiza sobre o crânio."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Intraoral Scan (Mesh)",
            "",
            "3D Mesh Files (*.stl *.ply *.obj)"
        )

        if file_path:
            try:
                # Usa o módulo mesh_manager para ler o STL/PLY/OBJ e jogar na 4ª janela
                self.mesh_manager.load_mesh(file_path)

                # Passa a malha pro Registration Manager
                self.registration_manager.set_mesh_actor(self.mesh_manager.mesh_actor)

                # Log de sucesso
                QMessageBox.information(
                    self,
                    "Scan Intraoral Importado",
                    f"Malha '{file_path.split('/')[-1]}' importada com sucesso no quadrante 3D."
                )

            except MeshManagerError as e:
                QMessageBox.critical(self, "Erro ao carregar Malha", str(e))
                print(f"Erro ao carregar malha intraoral: {str(e)}")
            except Exception as e:
                traceback.print_exc()
                QMessageBox.critical(self, "Erro Inesperado", f"Ocorreu um erro fatal ao carregar malha: {str(e)}")

    # -----------------------------
    # Tool Panel Events (Registration)
    # -----------------------------
    def on_mark_dicom_points(self):
        try:
            self.registration_manager.start_picking_dicom()
        except RegistrationManagerError as e:
            QMessageBox.warning(self, "Aviso", str(e))

    def on_mark_mesh_points(self):
        try:
            self.registration_manager.start_picking_mesh()
        except RegistrationManagerError as e:
            QMessageBox.warning(self, "Aviso", str(e))

    def on_align_landmarks(self):
        try:
            self.registration_manager.align_landmarks()
        except RegistrationManagerError as e:
            QMessageBox.warning(self, "Erro no Alinhamento", str(e))

    def on_refine_icp(self):
        try:
            # Avisar que pode demorar
            QApplication.setOverrideCursor(Qt.WaitCursor)
            self.registration_manager.refine_icp()
            QApplication.restoreOverrideCursor()
            QMessageBox.information(self, "Sucesso", "ICP finalizado com sucesso. Modelos alinhados!")
        except RegistrationManagerError as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.warning(self, "Erro no ICP", str(e))
        except Exception as e:
            QApplication.restoreOverrideCursor()
            traceback.print_exc()
            QMessageBox.critical(self, "Erro Fatal ICP", str(e))

    # -----------------------------
    # Tool Panel Events (Nerve Mapping)
    # -----------------------------
    def on_start_nerve_mapping(self):
        try:
            self.nerve_manager.start_mapping()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Erro ao Iniciar Mapeamento do Nervo", str(e))

    def on_undo_nerve_point(self):
        try:
            self.nerve_manager.undo_last_point()
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Erro ao Desfazer Ponto", str(e))

    def on_finish_nerve_mapping(self):
        try:
            self.nerve_manager.finish_mapping()
            QMessageBox.information(self, "Sucesso", "Mapeamento do Canal Mandibular finalizado.")
        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Erro ao Finalizar Mapeamento", str(e))

    # -----------------------------
    # Implant Manager Events
    # -----------------------------
    def on_add_implant(self):
        """Instancia um novo implante virtual 3D na cena."""
        try:
            # Pega as dimensões atuais da UI para criar o cilindro corretamente
            diameter = self.spin_diameter.value()
            length = self.spin_length.value()
            radius = diameter / 2.0

            # Adiciona o implante em uma coordenada inicial neutra
            # (No caso clínico, normalmente o ponto é extraído de um clique, mas começaremos no centro 0,0,0)
            self.implant_manager.add_implant(position=(0,0,0), radius=radius, length=length)

            # Reseta os spinners de rotação para zero (implante novo é sempre reto)
            self.spin_tilt.blockSignals(True)
            self.spin_pan.blockSignals(True)
            self.spin_tilt.setValue(0.0)
            self.spin_pan.setValue(0.0)
            self.spin_tilt.blockSignals(False)
            self.spin_pan.blockSignals(False)

        except Exception as e:
            traceback.print_exc()
            QMessageBox.critical(self, "Erro ao Adicionar Implante", str(e))

    def on_implant_parameter_changed(self):
        """Disparado quando o dentista clica na setinha de diâmetro, altura, etc."""
        try:
            diameter = self.spin_diameter.value()
            length = self.spin_length.value()
            tilt = self.spin_tilt.value()
            pan = self.spin_pan.value()

            self.implant_manager.update_active_implant(
                diameter=diameter,
                length=length,
                tilt=tilt,
                pan=pan
            )
        except Exception as e:
            print(f"Erro ao atualizar parâmetros: {str(e)}")

    def start_vtks(self):
        """Precisa ser chamado após o window.show() para inicializar os contextos OpenGL do VTK."""
        self.view_axial.start()
        self.view_sagittal.start()
        self.view_coronal.start()
        self.view_3d.start()


if __name__ == "__main__":
    app = QApplication(sys.argv)

    # Estilo escuro básico para o app
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    # Inicializa os interactors do VTK
    window.start_vtks()

    sys.exit(app.exec())
