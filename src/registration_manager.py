import vtk

class RegistrationManagerError(Exception):
    pass

class RegistrationManager:
    """
    Gerenciador de Registro de Imagens Médicas.
    Responsável por alinhar uma malha de superfície (Intraoral Scan - STL/PLY)
    com um volume 3D (DICOM/CBCT) usando um processo de 2 etapas:
    1. Landmark Registration (Alinhamento grosso por pontos fiduciais marcados pelo usuário)
    2. ICP - Iterative Closest Point (Refinamento automático da malha contra uma superfície óssea extraída do volume)
    """
    def __init__(self, interactor, renderer, render_window):
        self.interactor = interactor
        self.renderer = renderer
        self.render_window = render_window

        self.dicom_volume = None
        self.mesh_actor = None

        # Estruturas para armazenar os pontos clicados
        self.dicom_points = vtk.vtkPoints()
        self.mesh_points = vtk.vtkPoints()

        # Atores esféricos visuais para representar os cliques na tela
        self.dicom_point_actors = []
        self.mesh_point_actors = []

        # Picker de superfície geométrica para pegar a coordenada 3D exata do clique
        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.005)

        # Observers de clique (desativados por padrão)
        self.picking_dicom = False
        self.picking_mesh = False

        # Adicionar observer de clique esquerdo na janela 3D
        self.interactor.AddObserver("LeftButtonPressEvent", self._on_left_button_press)

        # Armazena a matriz de transformação combinada (Landmark + ICP)
        self.current_transform = vtk.vtkTransform()
        self.current_transform.PostMultiply()

    def set_dicom_volume(self, volume_data):
        """Define o vtkImageData (Tomografia)."""
        self.dicom_volume = volume_data

    def set_mesh_actor(self, actor):
        """Define o ator do Escaneamento Intraoral."""
        self.mesh_actor = actor
        # O Mesh Actor pode já ter uma matriz, então começamos com uma matriz identidade
        self.current_transform.Identity()
        if self.mesh_actor.GetUserTransform():
            self.current_transform.DeepCopy(self.mesh_actor.GetUserTransform())
        else:
            self.mesh_actor.SetUserTransform(self.current_transform)

    def start_picking_dicom(self):
        """Ativa o modo de clique para marcar pontos de referência no DICOM."""
        if not self.dicom_volume:
            raise RegistrationManagerError("DICOM não carregado no quadrante 3D.")
        self.picking_dicom = True
        self.picking_mesh = False
        print("Modo: Selecionando pontos no DICOM (Volume). Clique com o botão esquerdo.")

    def start_picking_mesh(self):
        """Ativa o modo de clique para marcar pontos de referência no STL."""
        if not self.mesh_actor:
            raise RegistrationManagerError("Malha Intraoral não carregada.")
        self.picking_mesh = True
        self.picking_dicom = False
        print("Modo: Selecionando pontos no STL (Malha). Clique com o botão esquerdo.")

    def stop_picking(self):
        """Desativa os modos de marcação manual."""
        self.picking_dicom = False
        self.picking_mesh = False

    def _on_left_button_press(self, obj, event):
        """Captura as coordenadas 3D onde o usuário clicou baseando-se no Picker."""
        if not self.picking_dicom and not self.picking_mesh:
            return

        click_pos = self.interactor.GetEventPosition()
        self.picker.Pick(click_pos[0], click_pos[1], 0, self.renderer)

        picked_pos = self.picker.GetPickPosition()

        # Se o picker não atingiu nada, a posição vem zerada.
        # (Um pequeno bug do VTK é que [0,0,0] pode ser válido, mas ignoramos para simplificar)
        if picked_pos == (0.0, 0.0, 0.0):
            return

        if self.picking_dicom:
            self.dicom_points.InsertNextPoint(picked_pos)
            self._add_visual_point(picked_pos, color=(1.0, 0.0, 0.0)) # Vermelho para DICOM
            print(f"Ponto DICOM adicionado: {picked_pos}. Total: {self.dicom_points.GetNumberOfPoints()}")

        elif self.picking_mesh:
            self.mesh_points.InsertNextPoint(picked_pos)
            self._add_visual_point(picked_pos, color=(0.0, 1.0, 0.0)) # Verde para STL
            print(f"Ponto STL adicionado: {picked_pos}. Total: {self.mesh_points.GetNumberOfPoints()}")

    def _add_visual_point(self, position, color):
        """Cria uma pequena esfera visual no local do clique."""
        sphereSource = vtk.vtkSphereSource()
        sphereSource.SetCenter(position)
        sphereSource.SetRadius(2.0)  # Esfera de 2mm para facilitar a visualização

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputConnection(sphereSource.GetOutputPort())

        actor = vtk.vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(color)

        self.renderer.AddActor(actor)
        self.render_window.Render()

        if color == (1.0, 0.0, 0.0):
            self.dicom_point_actors.append(actor)
        else:
            self.mesh_point_actors.append(actor)

    def align_landmarks(self):
        """
        Executa a Etapa 1: Landmark Registration (Coarse Fit).
        Encontra a matriz de transformação grosseira baseada nos pares de pontos selecionados.
        """
        if not self.mesh_actor or not self.dicom_volume:
            raise RegistrationManagerError("DICOM e Malha precisam estar carregados.")

        num_dicom = self.dicom_points.GetNumberOfPoints()
        num_mesh = self.mesh_points.GetNumberOfPoints()

        if num_dicom < 3 or num_mesh < 3:
            raise RegistrationManagerError("São necessários pelo menos 3 pontos em cada modelo.")

        if num_dicom != num_mesh:
            raise RegistrationManagerError(f"Número de pontos incompatível. DICOM: {num_dicom}, STL: {num_mesh}")

        print("Iniciando Alinhamento por Pontos (Landmark Transform)...")

        landmark_transform = vtk.vtkLandmarkTransform()
        landmark_transform.SetSourceLandmarks(self.mesh_points)
        landmark_transform.SetTargetLandmarks(self.dicom_points)
        landmark_transform.SetModeToRigidBody() # Transformação Rígida (Apenas Translação e Rotação, sem escala/deformação)
        landmark_transform.Update()

        # Concatena a transformação na matriz da malha de forma não-destrutiva
        self.current_transform.Concatenate(landmark_transform.GetMatrix())
        self.mesh_actor.SetUserTransform(self.current_transform)

        self.render_window.Render()
        print("Alinhamento por Pontos (Coarse Fit) Concluído.")

        # Limpar os pontos visuais após o alinhamento
        self.clear_points()

    def refine_icp(self):
        """
        Executa a Etapa 2: ICP - Iterative Closest Point (Fine Fit).
        Refina automaticamente o alinhamento da malha contra uma casca óssea extraída da tomografia.
        """
        if not self.mesh_actor or not self.dicom_volume:
            raise RegistrationManagerError("DICOM e Malha precisam estar carregados.")

        print("Extraindo casca óssea do DICOM (Marching Cubes) para o alvo do ICP...")

        # 1. Extração de Superfície (Marching Cubes)
        # O ICP exige malha contra malha. Extraímos o osso (aprox. 400 a 800 HU) para servir de Target.
        marching_cubes = vtk.vtkMarchingCubes()
        marching_cubes.SetInputData(self.dicom_volume)
        marching_cubes.SetValue(0, 500) # Isosuperfície em 500 HU (Esmalte/Osso Cortical)
        marching_cubes.Update()

        target_polydata = marching_cubes.GetOutput()

        if target_polydata.GetNumberOfPoints() == 0:
            raise RegistrationManagerError("Falha no Marching Cubes. Não foi possível extrair a superfície óssea do DICOM.")

        print("Aplicando transformada acumulada à malha fonte para iniciar o ICP próximo ao alvo...")

        # 2. Preparar a Malha de Origem (Source)
        # Precisamos aplicar a matriz do Landmark (Coarse Fit) na geometria antes de passar pro ICP
        transform_filter = vtk.vtkTransformPolyDataFilter()
        transform_filter.SetInputData(self.mesh_actor.GetMapper().GetInput())
        transform_filter.SetTransform(self.current_transform)
        transform_filter.Update()

        source_polydata = transform_filter.GetOutput()

        print("Iniciando ICP (Iterative Closest Point)...")

        # 3. O Motor ICP
        icp = vtk.vtkIterativeClosestPointTransform()
        icp.SetSource(source_polydata)
        icp.SetTarget(target_polydata)
        icp.GetLandmarkTransform().SetModeToRigidBody()
        icp.SetMaximumNumberOfIterations(100) # Limite seguro para não travar o app
        icp.SetMaximumMeanDistance(0.01) # Tolerância fina
        icp.StartByMatchingCentroidsOn()
        icp.Modified()
        icp.Update()

        print(f"ICP finalizado. RMSE Final: {icp.GetMeanDistance()}")

        # 4. Concatenar o refinamento do ICP na matriz de visualização da malha
        self.current_transform.Concatenate(icp.GetMatrix())
        self.mesh_actor.SetUserTransform(self.current_transform)

        self.render_window.Render()
        print("Alinhamento Fino (ICP) Concluído com Sucesso.")

    def clear_points(self):
        """Limpa as marcações de pontos da tela e das listas lógicas."""
        for actor in self.dicom_point_actors:
            self.renderer.RemoveActor(actor)
        for actor in self.mesh_point_actors:
            self.renderer.RemoveActor(actor)

        self.dicom_point_actors.clear()
        self.mesh_point_actors.clear()

        # Resetar as coordenadas lógicas
        self.dicom_points = vtk.vtkPoints()
        self.mesh_points = vtk.vtkPoints()

        self.stop_picking()
        self.render_window.Render()
