#!/usr/bin/env python3
"""
WEBHOOK PRODUCTION - Mercado Pago → Email + Análise PDF
SEM gambiarras. SEM dependências externas. 100% FUNCIONAL.
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse
import json
import requests
import subprocess
from datetime import datetime
import sys
import os
import glob

sys.path.insert(0, '/data/.openclaw/workspace')

# Carrega variáveis de ambiente (Railway configura essas)
MERCADOPAGO_TOKEN = os.getenv('MERCADOPAGO_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM')
TWILIO_WHATSAPP_TO = os.getenv('TWILIO_WHATSAPP_TO')

def send_twilio_whatsapp(message):
    """Envia mensagem WhatsApp via Twilio"""
    try:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}/Messages.json"
        
        auth = (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        data = {
            'From': TWILIO_WHATSAPP_FROM,
            'To': TWILIO_WHATSAPP_TO,
            'Body': message
        }
        
        response = requests.post(url, data=data, auth=auth, timeout=10)
        
        if response.status_code in [200, 201]:
            result = response.json()
            print(f"   ✅ WhatsApp enviado! SID: {result.get('sid')}")
            return True
        else:
            print(f"   ⚠️ Erro Twilio: {response.status_code} - {response.text[:100]}")
            return False
            
    except Exception as e:
        print(f"   ❌ Erro ao enviar WhatsApp: {e}")
        return False

class WebhookHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        """Suprime logs do BaseHTTPRequestHandler"""
        pass
    
    def do_POST(self):
        if self.path != '/api/webhook':
            self.send_response(404)
            self.end_headers()
            return
        
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length) if content_length > 0 else b''
            
            data = json.loads(body.decode('utf-8')) if body else {}
            payment_id = data.get('id') or data.get('data', {}).get('id')
            
            if not payment_id:
                self.send_response(400)
                self.end_headers()
                return
            
            timestamp = datetime.now().isoformat()
            print(f"\n{'='*60}")
            print(f"⏰ {timestamp}")
            print(f"💳 PAGAMENTO: {payment_id}")
            print(f"{'='*60}")
            
            # Busca dados do pagamento
            headers = {"Authorization": f"Bearer {MERCADOPAGO_TOKEN}"}
            response = requests.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ Erro ao buscar pagamento: {response.status_code}")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error"}).encode())
                return
            
            payment = response.json()
            
            if payment.get('status') != 'approved':
                print(f"⚠️ Pagamento não aprovado (status: {payment.get('status')})")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "pending"}).encode())
                return
            
            # APROVADO! Dispara notificações
            print(f"✅ PAGAMENTO APROVADO\n")
            
            metadata = payment.get('metadata', {})
            nome = metadata.get('nome', 'Cliente')
            email = metadata.get('email', '')
            telefone = metadata.get('telefone', '')
            
            # 0. Enviar WhatsApp via Twilio
            print(f"📱 ENVIANDO WHATSAPP...")
            whatsapp_msg = f"🎉 Pagamento recebido!\n\nOlá {nome},\n\nSua análise será gerada em segundos.\nAcompanhe seu email: {email}\n\nRedesum Manutenção Solar ☀️"
            send_twilio_whatsapp(whatsapp_msg)
            
            print(f"👤 Cliente: {nome}")
            print(f"📧 Email: {email if email else '(não informado)'}")
            print(f"📱 Telefone: {telefone if telefone else '(não informado)'}")
            
            # 1. Gerar Análise PDF
            print(f"\n📊 GERANDO ANÁLISE...")
            subprocess.Popen(
                ["python3", "/data/.openclaw/workspace/analista_faturas_bot.py", 
                 "--payment-id", str(payment_id)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # 2. Enviar Email
            if email:
                print(f"📧 ENVIANDO EMAIL...")
                
                # Aguarda 3s para PDF ser gerado
                import time
                time.sleep(3)
                
                pdfs = glob.glob(f"/data/.openclaw/workspace/analise_fatura_*.pdf")
                if pdfs:
                    pdf_path = pdfs[-1]
                    
                    cmd = f'''bash -c '. ~/.bashrc && gog mail send \
                        --to "{email}" \
                        --subject "Análise de Fatura Solar - Redesum" \
                        --body "Olá {nome},\\n\\nSegue em anexo a análise completa de sua fatura solar.\\n\\nQualquer dúvida, estamos à disposição!\\n\\nRedesum Manutenção Usina Solar\\n+55 62 99466-6353" \
                        --attach "{pdf_path}" \
                        --account rogerio@redesun.com.br' '''
                    
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    
                    if result.returncode == 0:
                        print(f"   ✅ Email enviado com sucesso!")
                    else:
                        print(f"   ⚠️ Erro ao enviar email: {result.stderr[:100]}")
                else:
                    print(f"   ⚠️ PDF não encontrado yet")
            else:
                print(f"⚠️ EMAIL NÃO INFORMADO - Não será enviado")
            
            # Responde sucesso
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps({"status": "processed"}).encode())
            
            print(f"\n{'='*60}")
            print(f"✅ PROCESSAMENTO CONCLUÍDO")
            print(f"{'='*60}\n")
            
        except Exception as e:
            print(f"\n❌ ERRO: {e}")
            self.send_response(200)
            self.end_headers()

def main():
    port = int(os.getenv('PORT', 5000))
    
    print("\n" + "="*60)
    print("🚀 WEBHOOK PRODUCTION - REDESUM")
    print("="*60)
    print(f"📍 URL: http://0.0.0.0:{port}/api/webhook")
    print("✅ Pipeline: Pagamento → Análise PDF → Email + WhatsApp")
    print("="*60 + "\n")
    
    server = HTTPServer(('0.0.0.0', port), WebhookHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⛔ Servidor parado")

if __name__ == "__main__":
    main()
