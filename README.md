# 📄 Lambda de Digitalização de Reclamações

Este Lambda é responsável por processar arquivos físicos de reclamações enviados via S3|Endpoint S3, extrair o conteúdo textual com Textract, identificar campos relevantes (nome, CPF, texto da reclamação) e enviar os dados para uma fila SQS para realizar classificação das categorias.

---

## 🚀 Funcionalidade

- Recebe eventos de upload no bucket `reclamacoes-aprocesssar`
- Aplica OCR com Textract para extrair texto do documento
- Identifica campos como `Nome`, `CPF` e `Reclamação`
- Grava os dados no banco de dados PostgreSQL
- Envia o payload para a fila `fila-reclamacoes-dev`
- Move o arquivo para o bucket `reclamacoes-digitalizadas` ou `reclamacoes-falhadas`

---

## 🧱 Arquitetura

- **Trigger:** Evento S3 (upload de arquivo)
- **OCR:** AWS Textract
- **Mensageria:** SQS (com DLQ configurada)
- **Persistência:** PostgreSQL via `pg8000`
- **Bucket de origem:** `reclamacoes-aprocesssar`
- **Bucket de destino:** `reclamacoes-digitalizadas` ou `reclamacoes-falhadas`

---

## 📦 Bibliotecas Utilizadas

| Biblioteca | Finalidade |
|------------|------------|
| `boto3`    | Acesso ao S3, SQS e Textract |
| `pg8000`   | Conexão com PostgreSQL |
| `re`       | Extração de campos via regex |
| `os`       | Manipulação de caminhos |
| `json`     | Manipulação de payloads |

---

## ⚙️ Configurações Importantes

- **DLQ ativa:** Mensagens que falham após 3 tentativas são enviadas para `fila-reclamacoes-digitalizacao-falhas`
- **Textract:** Utilizado para extrair texto de documentos físicos (PDF)
- **Banco:** Tabela `tb_reclamacoes` recebe os dados extraídos
- **SQS:** Payload enviado para `fila-reclamacoes-dev` para classificação posterior

---

## 🧪 Testes Realizados

- Enviar arquivos com diferentes formatos e campos para validar extração
- Simular falhas para verificar envio à DLQ
- Validar persistência no banco e envio correto para a fila

---
