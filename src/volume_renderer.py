import vtk

class VolumeRenderer:
    """
    Módulo responsável pela renderização volumétrica (Volume Rendering) 3D
    de imagens médicas em alta performance usando a GPU. Focado em visualização
    odontológica (tecidos ósseos e dentários).
    """
    def __init__(self, interactor):
        """
        Inicializa o renderizador de volume para o viewport 3D.

        Args:
            interactor: A instância do QVTKRenderWindowInteractor do viewport 3D.
        """
        self.interactor = interactor
        self.render_window = self.interactor.GetRenderWindow()

        # Limpar os renderizadores antigos (o cubo colorido da Fase 1)
        renderers = self.render_window.GetRenderers()
        renderers.InitTraversal()
        old_renderer = renderers.GetNextItem()
        if old_renderer:
            self.render_window.RemoveRenderer(old_renderer)

        # Criar o novo renderer dedicado à visualização 3D
        self.renderer = vtk.vtkRenderer()
        # Fundo padrão de softwares odontológicos (gradiente cinza/preto ou apenas preto/cinza escuro)
        self.renderer.SetBackground(0.1, 0.1, 0.1)
        self.render_window.AddRenderer(self.renderer)

        # Estilo de Interação 3D: Rotacionar, Pan e Zoom fluídos (Trackball)
        style = vtk.vtkInteractorStyleTrackballCamera()
        self.interactor.SetInteractorStyle(style)

        # Configuração do Mapper do Volume (Acelerado por GPU)
        # Extremamente crítico para navegabilidade fluida (60 FPS) de tomografias pesadas
        self.volume_mapper = vtk.vtkGPUVolumeRayCastMapper()

        # O volume em si (Ator)
        self.volume = vtk.vtkVolume()
        self.volume.SetMapper(self.volume_mapper)

        # Aplicar as propriedades de transferência de tecido ósseo ao volume
        self._setup_volume_properties()

        # Adiciona o volume ao cenário 3D
        self.renderer.AddVolume(self.volume)

    def _setup_volume_properties(self):
        """
        Configura as Funções de Transferência (Opacidade e Cor) baseadas
        nas Unidades Hounsfield (HU) de tecidos maxilofaciais.
        """
        self.volume_property = vtk.vtkVolumeProperty()

        # 1. Função de Opacidade (Scalar Opacity)
        # Onde o tecido é transparente (Ar/Gordura) e onde é opaco (Osso/Dente/Metal)
        opacity_transfer_function = vtk.vtkPiecewiseFunction()

        # Valores HU Clínicos de Odontologia aproximados:
        # Ar: -1000
        # Tecidos Moles: -200 a +100
        # Osso Trabecular (Medular): +150 a +400
        # Osso Cortical / Dentina / Esmalte: +400 a +2000

        # Filtramos tudo abaixo de 100 HU (Ar e tecidos moles não serão vistos)
        opacity_transfer_function.AddPoint(-500, 0.0)
        opacity_transfer_function.AddPoint(100, 0.0)

        # Transição rápida de opacidade (Para realçar a "casca" do osso cortical)
        opacity_transfer_function.AddPoint(300, 0.2)
        opacity_transfer_function.AddPoint(600, 0.8)
        opacity_transfer_function.AddPoint(1000, 1.0)

        self.volume_property.SetScalarOpacity(opacity_transfer_function)

        # 2. Função de Cores (Color Transfer)
        # Define as cores do renderizador com base na densidade
        color_transfer_function = vtk.vtkColorTransferFunction()

        # Cores para o "Bone Preset"
        # (Transição de vermelho escuro/marrom da medula para o off-white do esmalte/osso denso)
        color_transfer_function.AddRGBPoint(-500, 0.0, 0.0, 0.0)     # Preto
        color_transfer_function.AddRGBPoint(100, 0.73, 0.25, 0.11)   # Marrom/Carne (tecidos de transição)
        color_transfer_function.AddRGBPoint(300, 0.90, 0.82, 0.68)   # Bege/Marfim escuro (osso medular)
        color_transfer_function.AddRGBPoint(800, 1.0, 0.98, 0.93)    # Off-white brilhante (osso cortical / esmalte)
        color_transfer_function.AddRGBPoint(2000, 1.0, 1.0, 1.0)     # Branco puro (Ligas Metálicas / Implantes antigos)

        self.volume_property.SetColor(color_transfer_function)

        # 3. Shading (Sombreamento Dinâmico)
        # O Shading é vital para dar percepção de profundidade na anatomia 3D (ex: fóveas, forames, alvéolos)
        self.volume_property.ShadeOn()
        self.volume_property.SetAmbient(0.2)
        self.volume_property.SetDiffuse(0.7)
        self.volume_property.SetSpecular(0.3)
        self.volume_property.SetSpecularPower(10.0)

        # Interpolação Linear para eliminar o serrilhado dos voxels
        self.volume_property.SetInterpolationTypeToLinear()

        # Anexa as propriedades criadas ao ator volumétrico
        self.volume.SetProperty(self.volume_property)


    def set_volume(self, vtk_image_data):
        """
        Recebe o vtkImageData (já importado pelo SimpleITK) e joga para a GPU.

        Args:
            vtk_image_data: Objeto vtkImageData contendo a tomografia.
        """
        if not vtk_image_data:
            return

        # Alimenta o ray caster com os dados de voxels 3D
        self.volume_mapper.SetInputData(vtk_image_data)

        # Atualiza a câmera para focar perfeitamente no centro do crânio/mandíbula
        self.renderer.ResetCamera()

        # Garante que as luzes e o sombreador se reajustem ao novo volume
        self.renderer.ResetCameraClippingRange()

        # Atualiza o quadro da interface QT
        self.render_window.Render()
