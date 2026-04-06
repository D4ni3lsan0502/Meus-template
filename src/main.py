import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QWidget, QGridLayout, QVBoxLayout, QLabel
from PyQt5.QtCore import Qt
import vtk
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class VtkViewport(QWidget):
    """
    Widget customizado contendo uma janela de renderização VTK.
    """
    def __init__(self, title, bg_color, parent=None):
        super().__init__(parent)
        self.layout = QVBoxLayout(self)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)

        # Label de título
        self.title_label = QLabel(title)
        self.title_label.setAlignment(Qt.AlignCenter)
        self.title_label.setStyleSheet("background-color: #333; color: white; padding: 2px;")
        self.layout.addWidget(self.title_label)

        # Interactor VTK
        self.vtkWidget = QVTKRenderWindowInteractor(self)
        self.layout.addWidget(self.vtkWidget)

        # Configurar Renderer do VTK
        self.renderer = vtk.vtkRenderer()
        self.renderer.SetBackground(*bg_color)
        self.vtkWidget.GetRenderWindow().AddRenderer(self.renderer)

    def start(self):
        """Inicializa a janela VTK."""
        self.vtkWidget.Initialize()

class MainWindow(QMainWindow):
    """
    Janela Principal (Dental CAD).
    """
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Dental CAD - Planejamento 3D")
        self.resize(1280, 800)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        grid_layout = QGridLayout(central_widget)
        grid_layout.setContentsMargins(5, 5, 5, 5)
        grid_layout.setSpacing(5)

        # Criar os 4 viewports com cores de fundo levemente diferentes
        self.view_axial = VtkViewport("Axial", bg_color=(0.1, 0.12, 0.1))
        self.view_sagittal = VtkViewport("Sagittal", bg_color=(0.1, 0.1, 0.12))
        self.view_coronal = VtkViewport("Coronal", bg_color=(0.12, 0.1, 0.1))
        self.view_3d = VtkViewport("3D View", bg_color=(0.15, 0.15, 0.15))

        grid_layout.addWidget(self.view_axial, 0, 0)
        grid_layout.addWidget(self.view_3d, 0, 1)
        grid_layout.addWidget(self.view_coronal, 1, 0)
        grid_layout.addWidget(self.view_sagittal, 1, 1)

    def start_vtks(self):
        """Inicializa os interactors VTK após a janela principal ser exibida na tela."""
        self.view_axial.start()
        self.view_sagittal.start()
        self.view_coronal.start()
        self.view_3d.start()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    # Fundamental: Iniciar o VTK somente após o Qt renderizar a janela (evita falhas de contexto OpenGL)
    window.start_vtks()

    sys.exit(app.exec_())
