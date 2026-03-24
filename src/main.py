import sys
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QGridLayout,
    QVBoxLayout, QLabel, QFrame
)
from PySide6.QtCore import Qt
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

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
        self.setWindowTitle("Implant Planner - Hello World Médico (Fase 1)")
        self.resize(1024, 768)

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
