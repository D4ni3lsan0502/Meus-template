import os
import vtk

class MeshManagerError(Exception):
    """Exceção customizada para erros ao carregar malhas 3D intraorais."""
    pass

class MeshManager:
    """
    Gerenciador de Malhas de Superfície 3D (Intraoral Scans).
    Responsável por importar modelos odontológicos digitais (STL, OBJ, PLY)
    e renderizá-los sobrepostos ao volume DICOM no viewport 3D.
    """
    def __init__(self, renderer, render_window):
        """
        Inicializa o gerenciador de malhas vinculado ao viewport 3D.

        Args:
            renderer: O vtkRenderer do quadrante 3D (compartilhado com o VolumeRendering).
            render_window: O vtkRenderWindow para solicitar a atualização gráfica.
        """
        self.renderer = renderer
        self.render_window = render_window

        # Guardaremos a referência do ator da malha na classe,
        # pois na Fase 6 precisaremos aplicar matrizes de transformação geométrica (Registro).
        self.mesh_actor = None

    def load_mesh(self, file_path):
        """
        Lê um arquivo 3D dinamicamente pela extensão, cria o pipeline gráfico
        e adiciona o modelo de gesso/resina ao cenário 3D.

        Args:
            file_path (str): Caminho absoluto para o arquivo de malha intraoral.

        Raises:
            MeshManagerError: Em caso de formato não suportado ou falha de leitura.
        """
        if not os.path.isfile(file_path):
            raise MeshManagerError(f"Arquivo não encontrado: {file_path}")

        # 1. Identificar o leitor VTK apropriado via extensão do arquivo
        ext = file_path.lower().split('.')[-1]

        if ext == 'stl':
            reader = vtk.vtkSTLReader()
        elif ext == 'ply':
            reader = vtk.vtkPLYReader()
        elif ext == 'obj':
            reader = vtk.vtkOBJReader()
        else:
            raise MeshManagerError(f"Formato de malha não suportado: .{ext}. Use STL, PLY ou OBJ.")

        # Alimenta o leitor com o caminho do arquivo e executa a leitura
        reader.SetFileName(file_path)
        reader.Update()

        poly_data = reader.GetOutput()

        if poly_data.GetNumberOfPoints() == 0:
            raise MeshManagerError("A malha 3D importada está vazia ou corrompida.")

        # 2. Pipeline Gráfico: Converter geometria (PolyData) em primitivas gráficas
        mapper = vtk.vtkPolyDataMapper()
        mapper.SetInputData(poly_data)

        # Remover ator anterior se houver (para permitir re-importação limpa)
        if self.mesh_actor:
            self.renderer.RemoveActor(self.mesh_actor)

        # 3. Criar o Ator (Representação da malha no espaço 3D)
        self.mesh_actor = vtk.vtkActor()
        self.mesh_actor.SetMapper(mapper)

        # 4. Estética Odontológica (Modelo de Gesso / Resina de Escaneamento)
        property = self.mesh_actor.GetProperty()

        # Cor off-white / cinza claro
        property.SetColor(0.85, 0.85, 0.82)

        # Aumentar a difusão para refletir bastante luz (como gesso branco)
        property.SetDiffuse(0.8)

        # Adicionar especularidade pontual para realçar os detalhes finos
        # (cúspides, sulcos oclusais, fóveas) - simula o reflexo brilhante de resina/acrílico.
        property.SetSpecular(0.4)
        property.SetSpecularPower(30.0)

        # Suavização de Gouraud para não exibir as facetas duras dos triângulos da malha
        property.SetInterpolationToGouraud()

        # Adicionar a malha renderizada ao cenário compartilhado
        self.renderer.AddActor(self.mesh_actor)

        # 5. Atualizar a visualização
        # Força a câmera a reajustar para englobar tanto a mandíbula (volume) quanto o scan intraoral
        self.renderer.ResetCamera()
        self.render_window.Render()

        print(f"Malha importada com sucesso: {file_path}")
        print(f"Vértices: {poly_data.GetNumberOfPoints()}, Triângulos: {poly_data.GetNumberOfCells()}")
