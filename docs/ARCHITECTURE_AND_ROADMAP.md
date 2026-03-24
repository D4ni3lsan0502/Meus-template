# Software Architecture & Development Roadmap

## 1. System Architecture

### 1.1 Core Architecture Pattern: MVC/MVVM (Model-View-ViewModel)
Para garantir desacoplamento, testabilidade e performance, adotaremos a arquitetura **MVVM (Model-View-ViewModel)**. Isso é especialmente útil com frameworks como Qt (PyQt/PySide), onde a separação clara entre a interface e a lógica pesada de processamento 3D é essencial para manter a UI responsiva.

- **Model (Camada de Dados e Lógica Core)**:
  - Gerencia o estado do paciente, carregamento de DICOM/STL e lógica de implantes.
  - Implementado puramente em Python/C++ usando bibliotecas subjacentes (VTK, ITK, Open3D).
  - Executa as lógicas de processamento pesadas (segmentação, operações booleanas).

- **ViewModel (Camada de Apresentação)**:
  - Faz a ponte entre os Modelos médicos e a Interface Gráfica.
  - Converte dados de volume e malhas em "Atores" do VTK, que serão expostos à View.
  - Onde os Signals/Slots do Qt processam eventos de usuário (scroll do mouse nos planos ortogonais, cliques para posicionar implantes) e acionam comandos no Model.

- **View (Camada de UI)**:
  - A janela principal (Qt Main Window), contendo menus, toolbars e os widgets de renderização (QVTKRenderWindowInteractor).
  - Estritamente burra: não possui lógica médica, apenas lógica de exibição.

### 1.2 Tech Stack Definitiva Recomendada

Para um sistema de escala clínica (lidar com CTs de centenas de megabytes, operações booleanas complexas e renderização suave), a transição suave de Python para C++ é fundamental.

- **Fase de Prototipagem e Orquestração**: Python 3.10+
  - *Motivo:* Iteração rápida, excelente ecossistema para bibliotecas de visualização e machine learning, se necessário.

- **Interface Gráfica**: PySide6 (Qt for Python)
  - *Motivo:* Bindings oficiais da Qt Company, excelente performance, e integração robusta com C++ via Shiboken/SIP no futuro.

- **Renderização 3D e MPR**: VTK (Visualization Toolkit)
  - *Motivo:* O padrão ouro da indústria médica (usado no 3D Slicer, Paraview). Gerencia perfeitamente Volumes Rendering e Multiplanar Reconstruction (MPR) com aceleração de GPU.

- **Processamento de Imagem (DICOM)**: ITK (Insight Toolkit) e pydicom
  - *Motivo:* `pydicom` para metadados simples; `ITK` (via SimpleITK) para filtros robustos, segmentação de imagens e registro de volumes.

- **Processamento de Malhas (STL/Boolean Operations)**: Open3D / Trimesh (Python) -> **CGAL (C++)** no futuro.
  - *Motivo:* Trimesh é ótimo para operações básicas, mas para gerar o Guia Cirúrgico (operações booleanas perfeitas, offset de malhas para gerar "tubos" para anilhas), a biblioteca **CGAL** (Computational Geometry Algorithms Library) em C++ (empacotada com Pybind11 ou Swig) é imprescindível a médio prazo devido a problemas numéricos com outras bibliotecas open-source.

- **Performance Híbrida**: Pybind11
  - À medida que as operações de CAD (corte de guias, furos) ficarem lentas em Python, reescreveremos módulos específicos em C++ e os exportaremos como módulos Python com Pybind11.

---

## 2. Development Roadmap (Mapa de Desenvolvimento Iterativo)

A construção de um software tipo Blue Sky Plan será dividida em fases progressivas.

### Fase 1: Fundação do Visualizador (Hello World Médico) - **(Atual)**
- Configurar ambiente de desenvolvimento.
- Integrar PySide6 com VTK.
- Criar a Janela Principal com 4 viewports (Axial, Sagittal, Coronal e 3D).
- Sincronizar interações básicas de câmera.

### Fase 2: Ingestão de Dados e Visualização Básica
- Importação de série DICOM (`pydicom`, `SimpleITK`).
- Geração das visualizações de MPR (Multiplanar Reconstruction) nos 3 viewports 2D.
- Geração do Volume Rendering 3D usando Ray Casting do VTK.
- Leitura de arquivos STL/OBJ da arcada e sobreposição no ambiente 3D.

### Fase 3: Registro de Imagens (Alinhamento DICOM + STL)
- Seleção manual de pontos fiduciais pelo usuário na malha e na reconstrução óssea.
- Alinhamento inicial baseado em marcos (Landmark Registration).
- Refinamento de registro com algoritmo ICP (Iterative Closest Point).

### Fase 4: Planejamento Clínico (Nervo e Implantes)
- Ferramenta de desenho da curva panorâmica (Spline).
- Visualização do canal mandibular tubular (traçado manual do nervo alveolar).
- Biblioteca básica de implantes (Cilindros e cones paramétricos).
- Manipulação espacial (translação/rotação 3D) dos implantes dentro do osso e detecção de colisões.

### Fase 5: Design CAD do Guia Cirúrgico (Core Booleano)
- Ferramentas de seleção para delinear o perímetro do guia na malha gengival.
- Extrusão (Offset) da malha selecionada para gerar a "casca" do guia cirúrgico.
- Criação das anilhas (cylinders) baseadas nas posições e angulações dos implantes virtuais.
- **Operação Booleana Final:** União da casca do guia com as anilhas e subtração de cilindros internos para criar os furos reais da broca.
- Exportação da malha final para STL preparado para impressão 3D.

### Fase 6: Otimização em C++ e Polimento
- Migração de rotinas críticas (como a malha booleana final) para módulos em C++.
- Exportação de relatórios em PDF com protocolo cirúrgico.
- Sistema de licenças/tokens ou preparação para open-source estruturado.
