import os
import SimpleITK as sitk
import vtk
from vtkmodules.util import vtkImageImportFromArray

class DicomReaderError(Exception):
    """Exceção customizada para erros de leitura de DICOM."""
    pass

def read_dicom_series(directory_path):
    """
    Lê uma série de arquivos DICOM de um diretório usando SimpleITK.

    Args:
        directory_path (str): O caminho do diretório contendo os arquivos DICOM.

    Returns:
        sitk.Image: Um objeto de imagem SimpleITK representando o volume 3D.

    Raises:
        DicomReaderError: Se nenhum arquivo DICOM válido for encontrado.
    """
    print(f"Iniciando leitura do diretório DICOM: {directory_path}")

    # SimpleITK ImageSeriesReader permite ler séries inteiras agrupadas
    reader = sitk.ImageSeriesReader()

    # Pega a lista de séries (IDs) no diretório
    series_ids = reader.GetGDCMSeriesIDs(directory_path)
    if not series_ids:
        raise DicomReaderError(f"Nenhuma série DICOM encontrada no diretório: {directory_path}")

    # Usa a primeira série por padrão
    series_id = series_ids[0]
    file_names = reader.GetGDCMSeriesFileNames(directory_path, series_id)

    if not file_names:
        raise DicomReaderError(f"Nenhum arquivo encontrado para a série: {series_id}")

    reader.SetFileNames(file_names)

    # Carrega a imagem para a memória
    try:
        sitk_image = reader.Execute()
        print(f"Série carregada com sucesso. Dimensões: {sitk_image.GetSize()}, "
              f"Espaçamento: {sitk_image.GetSpacing()}")
        return sitk_image
    except Exception as e:
        raise DicomReaderError(f"Erro ao ler os arquivos DICOM: {str(e)}")


def sitk_to_vtk(sitk_image):
    """
    Converte um volume de imagem SimpleITK (sitk.Image) para vtkImageData.
    Mantém corretamente as informações espaciais de espaçamento e origem, essenciais
    para software CAD odontológico de precisão métrica.

    Args:
        sitk_image (sitk.Image): A imagem SimpleITK 3D.

    Returns:
        vtk.vtkImageData: Os dados de imagem VTK convertidos.
    """
    print("Convertendo sitk.Image para vtkImageData...")

    # 1. Extrair os pixels em um Numpy Array
    # Atenção: SimpleITK é [x, y, z], mas get_array_from_image retorna um array [z, y, x]
    nda = sitk.GetArrayFromImage(sitk_image)

    # 2. Utilizar o importador vtkImageImportFromArray
    # Essa função é a ponte segura e padronizada do VTK Python para Numpy arrays
    vtk_importer = vtkImageImportFromArray.vtkImageImportFromArray()
    vtk_importer.SetArray(nda)

    # Atenção com a correspondência entre os eixos ZYX do numpy e XYZ do VTK
    # vtkImageImportFromArray já lida com o formato padrão ZYX do numpy internamente,
    # mantendo os índices de dados no lugar correto para o VTK.

    # 3. Extrair os metadados espaciais críticos (spacing e origin)
    spacing = sitk_image.GetSpacing()
    origin = sitk_image.GetOrigin()

    # Note: sitk_image dimensions and spacing are ordered as X, Y, Z
    # Update importer
    vtk_importer.SetDataSpacing(spacing)
    vtk_importer.SetDataOrigin(origin)

    # Atualizar o pipe
    vtk_importer.Update()

    # Retornar a saída final de VTK
    vtk_data = vtk_importer.GetOutput()

    # IMPORTANTE: A função vtkImageImportFromArray não copia os dados da memória do array Numpy,
    # ela aponta diretamente para eles. Portanto, se `nda` ou `vtk_importer` forem destruídos (garbage collected)
    # no fim desta função, ocorrerá um SegFault na hora de renderizar em C++ (Fase 3).
    # Precisamos anexar as referências como atributos do objeto vtkImageData retornado
    # para mantê-las vivas na memória pelo mesmo tempo de vida do vtk_data.
    setattr(vtk_data, '_numpy_array_reference', nda)
    setattr(vtk_data, '_vtk_importer_reference', vtk_importer)

    # Informação para confirmar
    dims = vtk_data.GetDimensions()
    v_spacing = vtk_data.GetSpacing()
    print(f"Conversão concluída. vtkImageData Dimensões: {dims}, Espaçamento: {v_spacing}")

    return vtk_data
