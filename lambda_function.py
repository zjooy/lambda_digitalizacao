import boto3 
import json 
import re
import os
import pg8000

# Clientes AWS
s3 = boto3.client('s3')
sqs = boto3.client('sqs')
textract = boto3.client('textract')

# Configurações
QUEUE_URL = 'https://sqs.us-east-1.amazonaws.com/123456/fila-reclamacoes-dev'

def lambda_handler(event, context):
    try:
        print(f"-----Iniciando Lambda - RequestId: {context.aws_request_id}-----")
        processar_arquivo(event)
        return {
            'statusCode': 200,
            'body': 'Arquivo processado e enviado para SQS com sucesso.'
        }
    except Exception as e:
        print(f"Erro: {str(e)}")
        return {
            'statusCode': 500,
            'body': 'Erro ao processar o arquivo.'
        }

def processar_arquivo(event):
    bucket, key = extrair_dados_s3(event)
    arquivo = os.path.basename(key)

    texto = aplicar_textract(bucket, key)
    nome, cpf, reclamacao = extrair_campos(texto)

    caminho_anexo = key.replace('reclamacoes-aprocesssar/', 'reclamacoes-digitalizadas/')

    id_reclamacao = gravar_reclamacao(nome, cpf, reclamacao, caminho_anexo)

    if not id_reclamacao:
        mover_arquivo(bucket, key, sucesso=False)
        return

    payload = {
        "IdReclamacao": id_reclamacao,
        "Texto": reclamacao
    }

    print("Payload gerado:")
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    enviar_para_sqs(payload)
    mover_arquivo(bucket, key)


def extrair_dados_s3(event):
    record = event['Records'][0]
    bucket = record['s3']['bucket']['name']
    key = record['s3']['object']['key']
    return bucket, key

def aplicar_textract(bucket, key):
    response = textract.detect_document_text(
        Document={'S3Object': {'Bucket': bucket, 'Name': key}}
    )
    linhas = [b['Text'] for b in response['Blocks'] if b['BlockType'] == 'LINE']
    return '\n'.join(linhas)

def extrair_campos(texto):
    linhas = texto.split('\n')
    nome = "Desconhecido"
    cpf = "00000000000"
    reclamacao = ""

    texto_unificado = '\n'.join(linhas)

    # Nome
    nome_match = re.search(r'(?:Nome|Reclamante)\s*[:\-]?\s*(.+)', texto_unificado, re.IGNORECASE)
    if nome_match:
        nome = nome_match.group(1).strip()

    # CPF
    cpf_match = re.search(r'\d{3}\.?\d{3}\.?\d{3}-?\d{2}', texto_unificado)
    if cpf_match:
        cpf = cpf_match.group(0)

    # Reclamação (pega tudo após "Reclamacao:" até o próximo campo ou fim)
    reclamacao_match = re.search(r'Reclamacao\s*[:\-]?\s*(.+?)(?:\n[A-Z]|$)', texto_unificado, re.IGNORECASE | re.DOTALL)
    if reclamacao_match:
        reclamacao = reclamacao_match.group(1).strip()

    reclamacaoFormatada = reclamacao.replace('\n', ' ').strip()
    return nome, cpf, reclamacaoFormatada

def gravar_reclamacao(nome, cpf, texto, anexo):
    try:
        config = get_db_config()
        conn = pg8000.connect(
            user=config['username'],
            password=config['password'],
            host=config['host'],
            database=config['dbname'],
            port=int(config['port'])
        )

        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO tb_reclamacoes (nome, cpf, texto, canal, atendida, anexos, dataabertura)
                VALUES (%s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP)
                RETURNING IdReclamacao
            """, (nome, cpf, texto, 'fisico', False, json.dumps([anexo])))
            id_reclamacao = cur.fetchone()[0]

        conn.commit()
        conn.close()
        print(f"Reclamação {id_reclamacao} gravada com sucesso.")
        return id_reclamacao
    except Exception as e:
        print(f"Erro ao gravar reclamação: {str(e)}")
        enviar_para_fila_de_falha(json.dumps([anexo]), str(e))
        return None


def get_db_config():
    with open("db_config.json") as f:
        return json.load(f)

def enviar_para_sqs(mensagem):
    sqs.send_message(
        QueueUrl=QUEUE_URL,
        MessageBody=json.dumps(mensagem)
    )

def mover_arquivo(bucket, key, sucesso=True):
    print(f"Movendo arquivo: {key}")

    if "reclamacoes-aprocesssar/" not in key:
        print("Caminho original não contém 'reclamacoes-aprocesssar/'. Não será movido.")
        return

    if sucesso:
        destino = key.replace('reclamacoes-aprocesssar/', 'reclamacoes-digitalizadas/')
    else:
        destino = key.replace('reclamacoes-aprocesssar/', 'reclamacoes-falhadas/')

    print(f"Destino: {destino}")

    s3.copy_object(
        Bucket=bucket,
        CopySource={'Bucket': bucket, 'Key': key},
        Key=destino
    )
    s3.delete_object(Bucket=bucket, Key=key)

def enviar_para_fila_de_falha(arquivo, erro):
    print(f"Enviando para fila de falha: {id}, {arquivo}, {erro}")
    sqs.send_message(
        QueueUrl='https://sqs.us-east-1.amazonaws.com/12344455/fila-reclamacoes-digitalizacao-falhas',
        MessageBody=json.dumps({
            "Arquivo": arquivo,
            "Erro": erro
        })
    )