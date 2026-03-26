import sys
import traceback
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QVBoxLayout, QLabel, QFrame, QMenuBar, QMenu, QFileDialog, QMessageBox
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

from dicom_reader import read_dicom_series, sitk_to_vtk, DicomReaderError
from mpr_manager import MPRManager
from volume_renderer import VolumeRenderer
from mesh_manager import MeshManager, MeshManagerError

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
