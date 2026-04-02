import vtk
from vtkmodules.util.numpy_support import vtk_to_numpy, numpy_to_vtk
import trimesh
import numpy as np

class GuideGeneratorError(Exception):
    pass

class GuideGenerator:
    """
    Gerador de Guias Cirúrgicos Odontológicos (Surgical Guide CAD).
    Realiza o pipeline booleano pesado usando Trimesh (backend Manifold3D)
    para garantir que as operações não falhem em malhas anatômicas complexas.
    """
    def __init__(self, renderer, render_window):
        self.renderer = renderer
        self.render_window = render_window
        self.guide_actor = None

    def vtk_to_trimesh(self, polydata, transform=None):
        """Converte vtkPolyData para objeto trimesh.Trimesh aplicando a matriz geométrica."""
        if transform:
            # Aplica a transformação (ex: Registro ICP) nos vértices antes de exportar
            transform_filter = vtk.vtkTransformPolyDataFilter()
            transform_filter.SetInputData(polydata)
            transform_filter.SetTransform(transform)
            transform_filter.Update()
            polydata = transform_filter.GetOutput()

        vertices = vtk_to_numpy(polydata.GetPoints().GetData())

        # Extrair os triângulos de vtkCellArray (VTK 9+)
        # No VTK 9 a API mudou, os vértices não vêm mais interpolados com o tamanho '3'.
        # O ConnectivityArray traz os vértices sequenciais limpos [v1, v2, v3, v4, v5, v6...]
        connectivity = vtk_to_numpy(polydata.GetPolys().GetConnectivityArray())
        faces = connectivity.reshape((-1, 3))

        return trimesh.Trimesh(vertices=vertices, faces=faces, process=True)

    def trimesh_to_vtk(self, t_mesh):
        """Converte trimesh.Trimesh de volta para vtkPolyData para renderização."""
        polydata = vtk.vtkPolyData()

        # Vértices
        points = vtk.vtkPoints()
        # OBRIGATÓRIO deep=1 (Cópia Direta). Sem isso, o Numpy descarta `astype` imediatamente
        # e o pipeline C++ do VTK sofre SegFault ao atualizar as normais abaixo
        vtk_verts = numpy_to_vtk(t_mesh.vertices.astype(np.float32), deep=1)
        points.SetData(vtk_verts)
        polydata.SetPoints(points)

        # Faces (Triângulos)
        faces = t_mesh.faces
        # Recria o array no formato clássico VTK [3, v1, v2, v3...] para empacotar as células
        cells = np.column_stack((np.full(len(faces), 3), faces)).flatten()

        cell_array = vtk.vtkCellArray()
        # No VTK 9, numpy_to_vtkIdTypeArray deve ser usado para conectividade
        # (id_type parameter na numpy_to_vtk principal as vezes é deprecada dependendo da build)
        from vtkmodules.util.numpy_support import numpy_to_vtkIdTypeArray

        # OBRIGATÓRIO deep=1
        vtk_cells = numpy_to_vtkIdTypeArray(cells, deep=1)
        cell_array.SetCells(len(faces), vtk_cells)
        polydata.SetPolys(cell_array)

        # Gera as normais para o sombreamento ficar suave no VTK
        normals = vtk.vtkPolyDataNormals()
        normals.SetInputData(polydata)
        normals.ComputePointNormalsOn()
        normals.Update()

        return normals.GetOutput()

    def generate_guide(self, mesh_actor, implants, export_path, thickness=2.5, clearance=0.1):
        """
        Executa a Equação Booleana de Modelagem do Guia Cirúrgico.
        Passo A: Offset da Malha Dentária (Base do Guia).
        Passo B: União com os Tubos Guias (Anilhas).
        Passo C: Subtração dos Dentes (Encaixe Interno) e Furos da Broca.

        Args:
            mesh_actor: O ator VTK do escaneamento intraoral alinhado (Fase 6).
            implants: Lista de objetos VirtualImplant da Fase 8.
            export_path: Caminho de salvamento do arquivo .stl.
            thickness: Espessura da resina do guia cirúrgico em mm.
            clearance: Folga de encaixe em mm (impressora 3D).
        """
        if not mesh_actor or not mesh_actor.GetMapper() or not mesh_actor.GetMapper().GetInput():
            raise GuideGeneratorError("A malha intraoral (STL dos dentes) não foi carregada.")

        if not implants:
            raise GuideGeneratorError("Nenhum implante foi planejado. Adicione implantes antes de gerar o guia.")

        print("--- INICIANDO GERAÇÃO DO GUIA CIRÚRGICO ---")

        try:
            # 1. Extrair Malha Base (Dentes Originais)
            base_polydata = mesh_actor.GetMapper().GetInput()
            transform = mesh_actor.GetUserTransform()

            print("Convertendo Dentes (VTK) para Trimesh...")
            teeth_mesh = self.vtk_to_trimesh(base_polydata, transform)

            # Reparação básica caso a malha venha com furos/buracos simples
            if not teeth_mesh.is_watertight:
                print("Aviso: A malha intraoral não é Manifold (possui furos abertos). Tentando fechar via convex hull / preenchimento...")
                # Muitas vezes, um escaneamento intraoral é apenas uma "casca" aberta por baixo.
                # Precisaríamos de um fechamento planar robusto (planar hole filling), mas para
                # a prova de conceito, trimesh tentará o melhor com os backends disponíveis.
                teeth_mesh.fill_holes()

            # PASSO A: Criar a Resina Base (Offset Expansion)
            # Expandimos a malha dos dentes usando as normais dos vértices para fora.
            print(f"Passo A: Gerando Base de Resina (Espessura = {thickness}mm)...")

            # NOTA: Um offset robusto em malhas anatômicas abertas é extremamente complexo
            # e geralmente requer algoritmos de Voxelização/Minkowski sum.
            # Aqui fazemos um offset simples via normais (pode gerar auto-interseções em cantos agudos,
            # mas o Manifold3D backend do trimesh costuma lidar bem na booleana subsequente).
            offset_vertices = teeth_mesh.vertices + (teeth_mesh.vertex_normals * thickness)
            base_guide_mesh = trimesh.Trimesh(vertices=offset_vertices, faces=teeth_mesh.faces, process=True)

            # Preparar as Anilhas (Sleeves)
            print("Preparando Geometria das Anilhas (Sleeves e Drills)...")
            guide_tubes = []
            drill_holes = []

            for i, implant in enumerate(implants):
                # Pegar matriz absoluta do implante
                imp_transform = vtk.vtkTransform()
                implant.box_widget.GetTransform(imp_transform)
                vtk_mat = imp_transform.GetMatrix()

                # Construir matriz Numpy 4x4 (Elemento a elemento, pois vtkMatrix4x4 não é iterável pelo numpy_support)
                mat = np.eye(4)
                for r in range(4):
                    for c in range(4):
                        mat[r, c] = vtk_mat.GetElement(r, c)

                # Geometria do Furo Interno (Drill) - Onde a broca vai passar
                # Precisamos que o furo seja mais longo que o implante para varar o guia inteiro
                drill_radius = implant.radius + clearance
                drill_length = implant.length + 20.0 # 20mm a mais para furar o guia por cima e por baixo

                # ATENÇÃO ARQUITETURAL (VTK vs Trimesh):
                # O vtkCylinderSource gera cilindros orientados no eixo Y.
                # O trimesh.creation.cylinder gera orientados no eixo Z.
                # Para aplicarmos a mesma matriz matemática (mat) do implante VTK no trimesh,
                # DEVEMOS gerar o cilindro do trimesh no eixo Y.
                drill_segment = [[0, -drill_length/2.0, 0], [0, drill_length/2.0, 0]]
                drill = trimesh.creation.cylinder(radius=drill_radius, segment=drill_segment)

                # Aplica a matriz de translação/rotação do implante 3D
                drill.apply_transform(mat)
                drill_holes.append(drill)

                # Geometria do Tubo Guia (Anilha de Titânio/Resina)
                # Raio é o furo + 2mm de parede estrutural. A altura é menor, apenas a porção exposta acima do osso.
                tube_radius = drill_radius + 2.0
                tube_length = 6.0 # Anilha padrão clínica (6mm de altura cilíndrica visível)

                tube_segment = [[0, -tube_length/2.0, 0], [0, tube_length/2.0, 0]]
                tube = trimesh.creation.cylinder(radius=tube_radius, segment=tube_segment)

                # Precisamos levantar o tubo ao longo do seu próprio eixo Y (Onde o cilindro do VTK é gerado)
                # Para que ele fique "acima" do implante e encaixe na coroa dentária.
                offset_mat = np.eye(4)
                offset_mat[1, 3] = (implant.length / 2.0) + (tube_length / 2.0) + 1.0 # 1mm de distância da gengiva

                # Multiplica a matriz de posição global pela matriz de subida local
                final_tube_mat = np.dot(mat, offset_mat)
                tube.apply_transform(final_tube_mat)

                guide_tubes.append(tube)

            # PASSO B: União Booleana (UNION)
            # Fundimos a "Casca Gorda" (Base de Resina) com os Corpos das Anilhas
            print("Passo B: Fundindo Anilhas com a Base de Resina (UNION)...")

            # Concatenamos todas as malhas que vão ser unidas
            parts_to_union = [base_guide_mesh] + guide_tubes

            # Usando o backend robusto Manifold3D do trimesh
            union_mesh = trimesh.boolean.union(parts_to_union, engine='manifold')

            if union_mesh.is_empty:
                raise GuideGeneratorError("Falha na União Booleana (As malhas não colidiram corretamente).")

            # PASSO C: Subtração Booleana Crítica (DIFFERENCE)
            # Removemos a malha dos Dentes Originais (para encaixe interno na boca)
            # e removemos os Furos da Broca (para abrir o túnel dos implantes).
            print("Passo C: Esculpindo o Encaixe Interno e Furos da Broca (DIFFERENCE)...")

            # Expandimos minimamente a malha original do dente para gerar "Folga de Cimento/Encaixe"
            # O Guia não pode ter atrito zero senão não entra no paciente.
            clearance_vertices = teeth_mesh.vertices + (teeth_mesh.vertex_normals * clearance)
            teeth_clearance_mesh = trimesh.Trimesh(vertices=clearance_vertices, faces=teeth_mesh.faces, process=True)

            parts_to_subtract = [teeth_clearance_mesh] + drill_holes

            # Executa a Subtração Final
            final_guide_mesh = trimesh.boolean.difference([union_mesh] + parts_to_subtract, engine='manifold')

            if final_guide_mesh.is_empty:
                raise GuideGeneratorError("Falha na Subtração Booleana. O Guia resultante está vazio.")

            print("Matemática Booleana concluída.")

            # 3. Exportar STL
            print(f"Exportando Guia Cirúrgico para: {export_path}")
            final_guide_mesh.export(export_path)

            # 4. Renderizar o Guia Cirúrgico na Tela (Feedback Visual)
            print("Enviando malha final para a Placa de Vídeo (VTK)...")
            self._render_guide_vtk(final_guide_mesh)

            print("--- GUIA CIRÚRGICO GERADO COM SUCESSO ---")

        except Exception as e:
            raise GuideGeneratorError(f"Erro fatal durante as operações booleanas CAD: {str(e)}")

    def _render_guide_vtk(self, trimesh_guide):
        """Renderiza o objeto trimesh gerado de volta no viewport 3D como Verde Translúcido."""
        vtk_polydata = self.trimesh_to_vtk(trimesh_guide)

        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(vtk_polydata)

        # Limpar guia antigo se o usuário estiver regerando
        if self.guide_actor:
            self.renderer.RemoveActor(self.guide_actor)

        self.guide_actor = vtk.vtkActor()
        self.guide_actor.SetMapper(mapper)

        # Estética de Resina Cirúrgica (Verde Translúcido para aprovação final)
        prop = self.guide_actor.GetProperty()
        prop.SetColor(0.2, 0.8, 0.2) # Verde Cirúrgico
        prop.SetOpacity(0.6) # Translúcido para ver os dentes e implantes por dentro
        prop.SetSpecular(0.6)
        prop.SetDiffuse(0.7)

        self.renderer.AddActor(self.guide_actor)
        self.render_window.Render()
