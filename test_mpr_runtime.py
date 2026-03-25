import sys
from PySide6.QtWidgets import QApplication, QMainWindow
from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor
import vtk
from src.mpr_manager import MPRManager

# Setup basic Qt App
app = QApplication(sys.argv)
win = QMainWindow()

# Fake Interactors
i1 = QVTKRenderWindowInteractor(win)
i2 = QVTKRenderWindowInteractor(win)
i3 = QVTKRenderWindowInteractor(win)

# Instancia o manager
manager = MPRManager(i1, i2, i3)

# Cria um vtkImageData dummy compatível
img_data = vtk.vtkImageData()
img_data.SetDimensions(10, 10, 10)
img_data.SetSpacing(1.0, 1.0, 1.0)
img_data.AllocateScalars(vtk.VTK_FLOAT, 1)

# Passa o volume pro set_volume (Testa lógica do scalar range e cruz)
manager.set_volume(img_data)

print("Runtime Check concluído com sucesso!")
