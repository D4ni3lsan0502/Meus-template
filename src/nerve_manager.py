import vtk

class NerveManager:
    """
    Módulo responsável pelo Mapeamento do Canal Mandibular (Nervo Alveolar Inferior).
    Permite ao usuário clicar nas fatias MPR (2D) para gerar um trajeto 3D suave (Spline)
    com espessura volumétrica (Tubo de 3mm de diâmetro) que é renderizado
    simultaneamente nos 4 quadrantes da interface.
    """
    def __init__(self, interactors, renderers, render_windows):
        """
        Inicializa o gerenciador de mapeamento de nervo.

        Args:
            interactors (list): Lista de QVTKRenderWindowInteractors [Axial, Coronal, Sagital, 3D].
            renderers (list): Lista de vtkRenderers [Axial, Coronal, Sagital, 3D].
            render_windows (list): Lista de vtkRenderWindows [Axial, Coronal, Sagital, 3D].
        """
        self.interactors = interactors
        self.renderers = renderers
        self.render_windows = render_windows

        self.is_mapping = False

        # Estrutura para armazenar as coordenadas 3D dos cliques do usuário
        self.nerve_points = vtk.vtkPoints()

        # Atores esféricos visuais para representar cada clique individual nas telas
        self.control_point_actors = []

        # Setup do pipeline geométrico contínuo (A "Tubulação" do nervo)
        self._setup_nerve_pipeline()

        # O Picker de Ponto para obter a exata coordenada X,Y,Z do pixel clicado nas fatias MPR
        self.picker = vtk.vtkPointPicker()
        self.picker.SetTolerance(0.005)

        # Atrelar o evento de clique esquerdo aos três interactors MPR (índices 0, 1 e 2)
        # O viewport 3D (índice 3) geralmente não é usado para marcar o nervo (é interno ao osso)
        for i in range(3):
            self.interactors[i].AddObserver("LeftButtonPressEvent", self._on_left_click)

    def _setup_nerve_pipeline(self):
        """
        Constrói o pipeline VTK responsável por transformar uma nuvem de pontos
        em uma curva matemática suave (Spline) com espessura anatômica (Tubo).
        """
        # 1. A Matemática da Curva (vtkParametricSpline)
        # Gera uma curva contínua que passa suavemente por todos os pontos de controle
        self.spline = vtk.vtkParametricSpline()
        self.spline.SetPoints(self.nerve_points)
        self.spline.ClosedOff() # O nervo não é um círculo fechado

        # 2. Amostragem da Curva (Gerar os vértices finos do trajeto)
        self.spline_source = vtk.vtkParametricFunctionSource()
        self.spline_source.SetParametricFunction(self.spline)
        self.spline_source.SetUResolution(200) # Alta resolução geométrica para suavidade

        # 3. Geração do Volume do Nervo (vtkTubeFilter)
        # O nervo não é uma "linha fina", é um tubo espesso dentro do osso
        self.tube_filter = vtk.vtkTubeFilter()
        self.tube_filter.SetInputConnection(self.spline_source.GetOutputPort())
        # Raio de 1.5mm = 3.0mm de diâmetro (Padrão médio do canal alveolar inferior)
        self.tube_filter.SetRadius(1.5)
        self.tube_filter.SetNumberOfSides(20) # Resolução cilíndrica
        self.tube_filter.CappingOn() # Fecha as pontas do tubo

        # 4. Mapper
        self.tube_mapper = vtk.vtkPolyDataMapper()
        self.tube_mapper.SetInputConnection(self.tube_filter.GetOutputPort())

        # 5. Criar o Ator (vtkActor) único, que será compartilhado por todos os renderers
        self.nerve_actor = vtk.vtkActor()
        self.nerve_actor.SetMapper(self.tube_mapper)

        # Estética Odontológica (Material de Alerta)
        # Amarelo/Laranja vibrante totalmente opaco para contraste máximo contra o osso e a malha
        self.nerve_actor.GetProperty().SetColor(1.0, 0.8, 0.0) # Amarelo Dourado
        self.nerve_actor.GetProperty().SetOpacity(1.0)

        # Especularidade moderada para o tubo 3D parecer brilhante e volumoso
        self.nerve_actor.GetProperty().SetDiffuse(0.8)
        self.nerve_actor.GetProperty().SetSpecular(0.5)
        self.nerve_actor.GetProperty().SetSpecularPower(20.0)

        # Adicionar o mesmo Ator do Nervo em todos os 4 renderers
        # O VTK suporta que um único ator habite múltiplas vistas simultaneamente, otimizando a GPU.
        for renderer in self.renderers:
            renderer.AddActor(self.nerve_actor)

    def start_mapping(self):
        """Habilita a captura de pontos para desenhar o nervo mandibular."""
        self.is_mapping = True
        print("Modo: Mapeamento do Nervo Iniciado. Clique com o botão esquerdo nas fatias MPR.")

    def finish_mapping(self):
        """Finaliza a edição ativa do nervo, travando-o no lugar."""
        self.is_mapping = False
        print(f"Mapeamento do Nervo Finalizado. Total de pontos de controle: {self.nerve_points.GetNumberOfPoints()}")

    def _on_left_click(self, obj, event):
        """
        Captura a coordenada 3D exata baseada na fatia (slice) do volume
        onde o usuário clicou.
        """
        if not self.is_mapping:
            return

        interactor = obj

        # Encontra a qual renderer este interactor pertence
        idx = self.interactors.index(interactor)
        current_renderer = self.renderers[idx]

        # Pega a posição do clique na tela 2D
        click_pos = interactor.GetEventPosition()

        # Dispara o raio (picking) pelo volume
        self.picker.Pick(click_pos[0], click_pos[1], 0, current_renderer)
        picked_pos = self.picker.GetPickPosition()

        # Ignora clique no vazio
        if picked_pos == (0.0, 0.0, 0.0):
            return

        print(f"Ponto do nervo adicionado: {picked_pos}")

        # Adiciona o ponto à lista lógica
        self.nerve_points.InsertNextPoint(picked_pos)

        # Cria uma esfera para feedback visual imediato
        self._add_visual_control_point(picked_pos)

        # Re-calcula e re-desenha a Spline e o Tubo
        self._update_nerve_geometry()

    def _add_visual_control_point(self, position):
        """Cria uma pequena esfera (nó) no local exato do clique."""
        sphereSource = vtk.vtkSphereSource()
        sphereSource.SetCenter(position)
        sphereSource.SetRadius(0.8) # Um nó pequenininho vermelho para diferenciar do tubo amarelo

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphereSource.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(1.0, 0.0, 0.0) # Vermelho

        # Adiciona este controle visual em todas as views
        for renderer in self.renderers:
            renderer.AddActor(actor)

        self.control_point_actors.append(actor)

    def undo_last_point(self):
        """Desfaz o último ponto do nervo mapeado (Ctrl+Z do nervo)."""
        num_points = self.nerve_points.GetNumberOfPoints()

        if num_points == 0:
            print("Nenhum ponto de nervo para desfazer.")
            return

        # Remover último ator esférico de todas as telas
        last_actor = self.control_point_actors.pop()
        for renderer in self.renderers:
            renderer.RemoveActor(last_actor)

        # Remover o último ponto da lista lógica recriando a lista
        # (O VTK vtkPoints não tem método "RemoveLastPoint" fácil, precisamos reescrever)
        new_points = vtk.vtkPoints()
        for i in range(num_points - 1):
            new_points.InsertNextPoint(self.nerve_points.GetPoint(i))

        self.nerve_points = new_points
        self.spline.SetPoints(self.nerve_points)

        # Atualiza a tubulação
        self._update_nerve_geometry()
        print(f"Último ponto removido. Restantes: {self.nerve_points.GetNumberOfPoints()}")

    def _update_nerve_geometry(self):
        """
        Gatilho computacional que força o VTK a recalcular a spline matemática,
        gerar a nova malha cilíndrica do tubo e pedir o Refresh da interface em todos os quadrantes.
        """
        # Para que a Spline se forme, precisamos de pelo menos 2 pontos
        if self.nerve_points.GetNumberOfPoints() < 2:
            self.nerve_actor.SetVisibility(False)
        else:
            self.nerve_actor.SetVisibility(True)
            # Sinaliza que os pontos de base mudaram e o filtro precisa rodar de novo
            self.spline.Modified()
            self.spline_source.Update()
            self.tube_filter.Update()

        # Atualiza assíncronamente as 4 janelas da UI
        for window in self.render_windows:
            window.Render()
