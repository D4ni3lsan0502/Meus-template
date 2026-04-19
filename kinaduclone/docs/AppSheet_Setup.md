# Guia de Configuração - AppSheet

Este guia detalha como configurar a tabela `Catalogo_Atividades` importada do Google Sheets para o AppSheet, definindo os tipos de dados e criando a visualização do aplicativo.

## 1. Configuração da Data Table (Colunas e Tipos)

Após importar a planilha `Catalogo_Atividades.csv` para o Google Sheets e conectá-la ao AppSheet, vá até a aba **Data > Columns** e configure as propriedades de cada coluna da seguinte forma:

| Nome da Coluna | Tipo (Type) | Key | Label | Detalhes / Constraints |
| :--- | :--- | :---: | :---: | :--- |
| `ID_Atividade` | **Number** (ou Text) | ✅ Sim | ❌ Não | Desmarque *Show*. É o identificador único da linha. |
| `Nome_Atividade` | **Name** (ou Text) | ❌ Não | ✅ Sim | Marque *Require*. É o nome principal que aparecerá nas listas. |
| `Descricao` | **LongText** | ❌ Não | ❌ Não | Marque *Require*. Texto explicativo da atividade. |
| `Categoria` | **Enum** | ❌ Não | ❌ Não | Adicione os valores: `Motor`, `Motor Fino`, `Cognitivo`, `Linguagem`, `Socioemocional`. Defina como *Dropdown*. |
| `Idade_Minima_Dias` | **Number** | ❌ Não | ❌ Não | Idade mínima recomendada. |
| `Idade_Maxima_Dias` | **Number** | ❌ Não | ❌ Não | Idade máxima recomendada. |

*Dica: Você pode criar uma Coluna Virtual (Virtual Column) chamada `Idade_Recomendada_Meses` usando uma fórmula que divida os dias por 30 para facilitar a visualização para os pais, ex: `CONCATENATE([Idade_Minima_Dias]/30, " a ", [Idade_Maxima_Dias]/30, " meses")`.*

---

## 2. Configuração das Views (UX)

Vá até a aba **Views** para criar a interface do aplicativo.

### View 1: Catálogo Principal (Lista de Atividades)
1. Clique em **New View**.
2. **View name**: `Catálogo`
3. **For this data**: Selecione `Catalogo_Atividades`.
4. **View type**: Selecione **Deck** (ideal para exibir título e um resumo) ou **Card**.
5. **Position**: `Left` ou `Center`.
6. **View Options**:
   - *Group by*: `Categoria` (Isso organizará as atividades em seções como "Motor", "Cognitivo", etc.).
   - *Primary header*: `Nome_Atividade`.
   - *Secondary header*: `Categoria` ou a sua coluna virtual de Idade em Meses.
   - *Summary column*: Pode ser deixado em branco ou usar um ícone.
7. Clique em **Save**.

### View 2: Detalhes da Atividade
Esta view é gerada automaticamente pelo AppSheet (geralmente chamada de `Catalogo_Atividades_Detail`).
1. Em **Views**, encontre `Catalogo_Atividades_Detail` (sob *System Views*).
2. **Column order**: Defina a ordem como:
   1. `Nome_Atividade`
   2. `Categoria`
   3. `Descricao`
   4. `Idade_Minima_Dias`
   5. `Idade_Maxima_Dias`
3. **Quick Edit columns**: Opcional, se você quiser que os usuários possam editar a categoria ou descrição diretamente da tela de detalhes.

---

## 3. Próximos Passos (Avançado)
- **Filtros (Slices)**: Crie *Slices* em **Data > Slices** para mostrar apenas atividades para a idade atual da criança (ex: `[Idade_Minima_Dias] <= [Idade_Crianca] AND [Idade_Maxima_Dias] >= [Idade_Crianca]`).
- **Ações**: Crie um botão (Action) "Concluir Atividade" que registre a data de conclusão em uma tabela separada de histórico (ex: tabela `Progresso_Crianca`).
