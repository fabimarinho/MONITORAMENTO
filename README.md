# 🌐 MONITORAMENTO de Sites e Serviços

Este projeto em Python é um sistema de **monitoramento automatizado** e **geração de relatórios** para verificar a disponibilidade e o status de sites e serviços web. Ele utiliza agendamento em segundo plano para realizar checagens periódicas e notificar sobre falhas, além de gerar relatórios diários e mensais de desempenho.

## 🌟 Funcionalidades Principais

*   **Checagem Periódica de Sites:** Verifica o status de URLs configuradas em intervalos regulares.
*   **Notificações de Falha:** Envia alertas de erro (provavelmente via Slack, conforme sugerido pelo `utils.py`).
*   **Geração de Relatórios:** Cria relatórios diários e mensais de disponibilidade e tempo de atividade.
*   **Configuração Flexível:** Permite a fácil customização dos sites a serem monitorados, intervalos de checagem e horários de relatório.

## 🛠️ Tecnologias Utilizadas

O projeto é desenvolvido em **Python** e utiliza as seguintes bibliotecas principais (inferidas a partir da estrutura do código):

*   **`apscheduler`**: Para agendamento de tarefas em segundo plano (checagens e relatórios).
*   **`datetime` / `pytz`**: Para manipulação de datas e fusos horários.
*   **Módulos customizados:** `config`, `check`, `report`, `utils` para modularizar a lógica de configuração, checagem, geração de relatórios e utilitários (como envio de notificações).

## 🚀 Como Configurar e Rodar

### Pré-requisitos

Certifique-se de ter o **Python 3.x** instalado em seu sistema.

### 1. Clonar o Repositório

```bash
git clone https://github.com/fabimarinho/MONITORAMENTO.git
cd MONITORAMENTO/NOVO_MONITORAMENTO
```

### 2. Instalar Dependências

Embora o `requirements.txt` esteja vazio, as dependências essenciais para o funcionamento do agendador e da lógica de checagem devem ser instaladas.

```bash
# Exemplo de instalação das dependências inferidas:
pip install apscheduler requests pytz
```
*Recomenda-se preencher o arquivo `requirements.txt` com as dependências exatas do projeto.*

### 3. Configuração

O projeto utiliza um arquivo de configuração (`config.py`) e provavelmente variáveis de ambiente (`.env`).

1.  **Configuração de Sites:** Edite o arquivo `config.py` ou crie um arquivo `.env` para definir as URLs a serem monitoradas, o intervalo de checagem e os detalhes de notificação (como o webhook do Slack).

    *   **Exemplo de Configurações (a ser ajustado no `config.py`):**
        ```python
        # Intervalo de checagem em horas (pode ser ajustado para minutos/segundos)
        CHECK_INTERVAL_HOURS = 1
        
        # Fuso horário para agendamento
        TIMEZONE = 'America/Sao_Paulo'
        
        # Hora para geração do relatório diário
        DAILY_REPORT_HOUR = 9
        
        # Configurações de notificação (ex: Slack Webhook)
        SLACK_WEBHOOK_URL = 'SUA_URL_DO_SLACK'
        ```

### 4. Executar o Sistema

Inicie o sistema de monitoramento executando o arquivo principal:

```bash
python main.py
```

O sistema será executado em *background* e começará a realizar as checagens e gerar os relatórios conforme a agenda definida.

## 📁 Estrutura do Projeto

A estrutura principal do código está organizada da seguinte forma:

```
MONITORAMENTO/
├── NOVO_MONITORAMENTO/
│   ├── main.py             # Ponto de entrada do sistema e agendamento
│   ├── check.py            # Lógica para checar o status dos sites
│   ├── report.py           # Lógica para gerar os relatórios (diários/mensais)
│   ├── config.py           # Configurações do sistema (URLs, intervalos, etc.)
│   ├── utils.py            # Funções utilitárias (ex: envio de notificações)
│   ├── requirements.txt    # Lista de dependências Python
│   └── relatorio/          # Diretório para saída dos relatórios gerados
└── relatorio/              # Diretório de relatórios (duplicado/histórico)
```

## 🤝 Contribuição

Contribuições são bem-vindas! Sinta-se à vontade para abrir *issues* para reportar bugs ou sugerir novas funcionalidades, e enviar *Pull Requests* com melhorias.




