import vtk

class MPRManager:
    """
    Gerenciador de Reconstrução Multiplanar (MPR).
    Responsável por fatiar um volume vtkImageData em três planos ortogonais (Axial, Coronal e Sagital)
    e renderizar esses planos nas janelas correspondentes do PyQt (QVTKRenderWindowInteractor),
    mantendo os 3 visualizadores sincronizados via vtkResliceCursor.
    """
    def __init__(self, interactor_axial, interactor_coronal, interactor_sagittal):
        self.volume_data = None

        # O ResliceCursor é o coração do MPR: ele mantém a interseção (cruz) dos 3 planos sincronizada
        self.reslice_cursor = vtk.vtkResliceCursor()
        self.reslice_cursor.SetThickness(1.5, 1.5, 1.5)

        # As três visualizações (0 = Sagital, 1 = Coronal, 2 = Axial) padronizadas pelo VTK
        self.viewers = []
        interactors = [interactor_sagittal, interactor_coronal, interactor_axial]

        for i in range(3):
            interactor = interactors[i]

            # Limpar o renderer placeholder (o cubo colorido da Fase 1)
            render_window = interactor.GetRenderWindow()
            renderers = render_window.GetRenderers()
            renderers.InitTraversal()
            old_renderer = renderers.GetNextItem()
            if old_renderer:
                render_window.RemoveRenderer(old_renderer)

            # vtkResliceImageViewer é o container completo para a imagem fatiada
            viewer = vtk.vtkResliceImageViewer()

            # IMPORTANTÍSSIMO: Força o viewer a usar a janela Qt existente,
            # senão ele abre janelas C++ pop-ups nativas separadas.
            viewer.SetRenderWindow(render_window)
            viewer.SetupInteractor(interactor)

            # Configura a orientação padrão baseada no índice do loop
            if i == 0:
                viewer.SetSliceOrientationToYZ()  # Sagital
            elif i == 1:
                viewer.SetSliceOrientationToXZ()  # Coronal
            elif i == 2:
                viewer.SetSliceOrientationToXY()  # Axial

            # Interpolador linear suave para imagens médicas
            viewer.GetImageActor().GetProperty().SetInterpolationTypeToLinear()

            # Widget do cursor (a cruz interativa)
            viewer.GetResliceCursorWidget().GetRepresentation().GetResliceCursorActor().GetCursorAlgorithm().SetResliceCursor(self.reslice_cursor)

            # Eventos interativos para scroll do mouse mudarem a fatia sem aplicar Zoom
            # (vtkResliceCursorWidget tem seu próprio style nativo)
            interactor.RemoveObservers("MouseWheelForwardEvent")
            interactor.RemoveObservers("MouseWheelBackwardEvent")
            interactor.AddObserver("MouseWheelForwardEvent", self.scroll_slice_forward)
            interactor.AddObserver("MouseWheelBackwardEvent", self.scroll_slice_backward)

            # Observer para sincronizar a cruz (cursor) sempre que ele for arrastado pelo usuário em qualquer tela
            viewer.GetResliceCursorWidget().AddObserver("InteractionEvent", self.sync_viewers)

            self.viewers.append(viewer)

    def set_volume(self, vtk_image_data):
        """
        Carrega o volume DICOM (vtkImageData) nos três viewports MPR e centraliza.
        """
        self.volume_data = vtk_image_data

        # Alimentar o ResliceCursor (Motor do MPR) com a imagem base
        self.reslice_cursor.SetImage(self.volume_data)
        self.reslice_cursor.SetCenter(self.volume_data.GetCenter())
        self.reslice_cursor.Update()

        # Calcular o Window/Level baseado nas Unidades Hounsfield (HU) do DICOM
        # Evita a tela "toda branca" que ocorreria com o range padrão 0-255.
        scalar_range = self.volume_data.GetScalarRange()
        min_val, max_val = scalar_range[0], scalar_range[1]

        # Definir Window (largura) e Level (centro) de forma segura
        window = max_val - min_val
        level = min_val + window / 2.0

        for viewer in self.viewers:
            viewer.SetInputData(self.volume_data)

            # Aplicar contraste / brilho reais da imagem
            viewer.SetColorWindow(window)
            viewer.SetColorLevel(level)

            # Ligar e atualizar a cruz na tela
            viewer.GetResliceCursorWidget().On()

            # Resetar câmera para enquadrar a anatomia perfeitamente
            viewer.GetRenderer().ResetCamera()
            viewer.Render()

        # Sincronizar todos
        self.sync_viewers(None, None)

    def sync_viewers(self, obj, event):
        """
        Garante que ao mexer no cursor (cruz) em uma tela, as outras acompanhem.
        """
        for viewer in self.viewers:
            viewer.Render()

    def scroll_slice_forward(self, interactor, event):
        """Avança uma fatia na direção do plano ativo."""
        viewer = self._get_viewer_from_interactor(interactor)
        if viewer and self.volume_data:
            current_slice = viewer.GetSlice()
            if current_slice < viewer.GetSliceMax():
                viewer.SetSlice(current_slice + 1)
                self.sync_viewers(None, None)

    def scroll_slice_backward(self, interactor, event):
        """Recua uma fatia na direção do plano ativo."""
        viewer = self._get_viewer_from_interactor(interactor)
        if viewer and self.volume_data:
            current_slice = viewer.GetSlice()
            if current_slice > viewer.GetSliceMin():
                viewer.SetSlice(current_slice - 1)
                self.sync_viewers(None, None)

    def _get_viewer_from_interactor(self, interactor):
        for viewer in self.viewers:
            if viewer.GetInteractor() == interactor:
                return viewer
        return None
