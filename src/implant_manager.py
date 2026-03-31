import vtk

class VirtualImplant:
    """
    Representa um único Implante Odontológico Virtual paramétrico.
    Inclui o corpo do implante (Titânio) e uma zona de segurança cilíndrica translúcida (Vermelha).
    Permite movimentação interativa 3D via vtkBoxWidget.
    """
    def __init__(self, manager, interactor_3d, position=(0,0,0), radius=2.0, length=10.0, safety_margin=1.5):
        self.manager = manager
        self.interactor_3d = interactor_3d

        self.radius = radius
        self.length = length
        self.safety_margin = safety_margin

        # Guardaremos os valores absolutos de rotação do UI para não acumular
        self.current_tilt = 0.0
        self.current_pan = 0.0

        # Guarda a posição base da caixa para aplicar rotações limpas
        self.base_position = position

        # 1. Geometria Dinâmica do Implante (Corpo de Titânio)
        self.implant_source = vtk.vtkCylinderSource()
        self.implant_source.SetResolution(30)
        self.implant_source.SetRadius(self.radius)
        self.implant_source.SetHeight(self.length)

        implant_mapper = vtk.vtkPolyDataMapper()
        implant_mapper.SetInputConnection(self.implant_source.GetOutputPort())

        self.implant_actor = vtk.vtkActor()
        self.implant_actor.SetMapper(implant_mapper)
        self.implant_actor.SetPosition(position)

        # Estética do Implante (Titânio Metálico Brilhante)
        prop = self.implant_actor.GetProperty()
        prop.SetColor(0.7, 0.7, 0.75) # Prata / Titânio
        prop.SetAmbient(0.3)
        prop.SetDiffuse(0.6)
        prop.SetSpecular(0.8)
        prop.SetSpecularPower(50.0)

        # 2. Geometria da Zona de Segurança Clínica
        # Cilindro concêntrico para alertar invasão do nervo alveolar ou dentes vizinhos
        self.safety_source = vtk.vtkCylinderSource()
        self.safety_source.SetResolution(20)
        self._update_safety_geometry()

        safety_mapper = vtk.vtkPolyDataMapper()
        safety_mapper.SetInputConnection(self.safety_source.GetOutputPort())

        self.safety_actor = vtk.vtkActor()
        self.safety_actor.SetMapper(safety_mapper)
        self.safety_actor.SetPosition(position)

        # Estética da Zona de Segurança (Vermelho Translúcido de Alerta)
        safety_prop = self.safety_actor.GetProperty()
        safety_prop.SetColor(1.0, 0.0, 0.0)
        safety_prop.SetOpacity(0.3) # Translúcido
        safety_prop.SetRepresentationToWireframe() # Ou sólido translúcido, Wireframe ajuda a ver dentro
        safety_prop.SetLineWidth(1.0)

        # O ator de segurança copia a matriz geométrica do implante principal
        # (Para que rotacionem e transladem juntos perfeitamente)
        self.safety_actor.SetUserTransform(self.implant_actor.GetUserTransform())

        # 3. Controle Interativo 3D (O Widget de Arraste Invisível)
        # O BoxWidget envolve o implante e permite translação e rotação com o mouse
        self.box_widget = vtk.vtkBoxWidget()
        self.box_widget.SetInteractor(self.interactor_3d)
        self.box_widget.SetProp3D(self.implant_actor)
        self.box_widget.SetPlaceFactor(1.25)
        self.box_widget.PlaceWidget()

        # Esconder as arestas e alças do BoxWidget para manter a interface limpa
        # O usuário clica diretamente no implante e arrasta
        self.box_widget.GetOutlineProperty().SetOpacity(0.0)
        self.box_widget.GetSelectedOutlineProperty().SetOpacity(0.0)
        self.box_widget.GetHandleProperty().SetOpacity(0.0)

        self.box_widget.On()
        self.box_widget.AddObserver("InteractionEvent", self._on_interaction)

    def _update_safety_geometry(self):
        """Recalcula o tamanho da zona de segurança baseada no tamanho atual do implante."""
        self.safety_source.SetRadius(self.radius + self.safety_margin)
        self.safety_source.SetHeight(self.length + self.safety_margin)
        self.safety_source.Update()

    def update_parameters(self, radius=None, length=None):
        """Atualiza a geometria parametrizada via código/UI."""
        if radius is not None:
            self.radius = radius
            self.implant_source.SetRadius(self.radius)

        if length is not None:
            self.length = length
            self.implant_source.SetHeight(self.length)

        if radius is not None or length is not None:
            self.implant_source.Update()
            self._update_safety_geometry()

            # Reposiciona o widget interativo para englobar o novo tamanho
            self.box_widget.PlaceWidget()
            self.manager._request_render()

    def apply_rotation(self, tilt=0.0, pan=0.0):
        """
        Aplica rotações absolutas específicas nos eixos X (Tilt) e Y (Pan).
        Em vez de concatenar, nós calculamos o Delta e aplicamos sobre a matriz atual,
        ou melhor: reconstruímos a matriz de rotação baseando-se no centro atual.
        """
        # Calcula a diferença entre o que a UI está mandando agora e o que nós já temos
        delta_tilt = tilt - self.current_tilt
        delta_pan = pan - self.current_pan

        # Se não houve mudança real de ângulo, não fazemos nada (evita o bug de spin infinito ao mudar raio)
        if delta_tilt == 0.0 and delta_pan == 0.0:
            return

        # Atualiza o estado
        self.current_tilt = tilt
        self.current_pan = pan

        transform = vtk.vtkTransform()
        self.box_widget.GetTransform(transform)

        pos = transform.GetPosition()

        # Cria a matriz aplicando apenas a diferença angular
        delta_transform = vtk.vtkTransform()
        delta_transform.PostMultiply()
        delta_transform.Translate(-pos[0], -pos[1], -pos[2])
        delta_transform.RotateX(delta_tilt)
        delta_transform.RotateY(delta_pan)
        delta_transform.Translate(pos[0], pos[1], pos[2])

        delta_transform.Concatenate(transform)

        self.box_widget.SetTransform(delta_transform)
        self._on_interaction(self.box_widget, None)

    def _on_interaction(self, widget, event):
        """Callback disparado sempre que o usuário arrasta/rotaciona o implante na tela 3D."""
        transform = vtk.vtkTransform()
        widget.GetTransform(transform)

        # Sincroniza o corpo de titânio
        self.implant_actor.SetUserTransform(transform)

        # Sincroniza a zona de alerta vermelha
        self.safety_actor.SetUserTransform(transform)

        # Solicita atualização aos 4 quadrantes (Axial, Sagital, Coronal, 3D)
        self.manager._request_render()

    def get_actors(self):
        """Retorna os atores VTK que representam este implante."""
        return [self.implant_actor, self.safety_actor]


class ImplantManager:
    """
    Gerenciador Global do Planejamento de Implantes.
    Controla uma frota de implantes virtuais espalhados pela mandíbula/maxila,
    garantindo que sejam desenhados simultaneamente em todas as fatias MPR e no espaço 3D.
    """
    def __init__(self, interactors, renderers, render_windows):
        self.interactor_3d = interactors[3] # Interactor da janela 3D (Bottom-Right)
        self.renderers = renderers
        self.render_windows = render_windows

        self.implants = []
        self.active_implant_index = -1

    def add_implant(self, position=(0, 0, 0), radius=2.0, length=10.0):
        """
        Gera um novo implante virtual e o anexa a todos os 4 viewports do PyQt.
        """
        implant = VirtualImplant(
            manager=self,
            interactor_3d=self.interactor_3d,
            position=position,
            radius=radius,
            length=length
        )

        self.implants.append(implant)
        self.active_implant_index = len(self.implants) - 1

        # Anexa os novos atores aos 4 cenários gráficos (Viewport Axial, Sagital, Coronal e 3D)
        for renderer in self.renderers:
            for actor in implant.get_actors():
                renderer.AddActor(actor)

        self._request_render()
        print(f"Implante {self.active_implant_index} adicionado no local {position}.")
        return self.active_implant_index

    def update_active_implant(self, diameter=None, length=None, tilt=None, pan=None):
        """
        Aplica as alterações dos Spinboxes da UI (Raio, Altura, Inclinação)
        ao implante atualmente selecionado.
        """
        if self.active_implant_index < 0 or self.active_implant_index >= len(self.implants):
            return

        implant = self.implants[self.active_implant_index]

        radius = diameter / 2.0 if diameter is not None else None
        implant.update_parameters(radius=radius, length=length)

        # Apply absolute rotation updates explicitly to avoid infinite spin bugs
        if tilt is not None or pan is not None:
            implant.apply_rotation(
                tilt=tilt if tilt is not None else implant.current_tilt,
                pan=pan if pan is not None else implant.current_pan
            )

    def _request_render(self):
        """Força o redesenho assíncrono das 4 telas do Qt."""
        for window in self.render_windows:
            window.Render()
