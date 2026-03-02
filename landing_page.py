#!/usr/bin/env python3
"""
Landing Page + Webhook Handler
Serve HTML na raiz (GET) e processa pagamentos (POST)
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
import requests
import subprocess
import os
from datetime import datetime
import glob
import time

MERCADOPAGO_TOKEN = os.getenv('MERCADOPAGO_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
TWILIO_WHATSAPP_TO = os.getenv('TWILIO_WHATSAPP_TO', 'whatsapp:+5562993156662')

HTML_LANDING = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Auditoria de Faturas Solar - Redesum</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); min-height: 100vh; display: flex; align-items: center; justify-content: center; padding: 20px; }
        .container { background: white; border-radius: 12px; box-shadow: 0 20px 60px rgba(0,0,0,0.3); max-width: 500px; width: 100%; padding: 40px; }
        h1 { color: #333; margin-bottom: 10px; font-size: 28px; }
        .subtitle { color: #666; margin-bottom: 30px; font-size: 14px; }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #333; font-weight: 600; font-size: 14px; }
        input, textarea { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 14px; font-family: inherit; transition: border-color 0.3s; }
        input:focus, textarea:focus { outline: none; border-color: #667eea; }
        button { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; transition: transform 0.2s; }
        button:hover { transform: scale(1.02); }
        .info { background: #f0f4ff; padding: 15px; border-radius: 6px; margin-bottom: 20px; font-size: 13px; color: #555; line-height: 1.6; }
        .price { text-align: center; font-size: 24px; color: #667eea; font-weight: 700; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>☀️ Auditoria de Fatura Solar</h1>
        <p class="subtitle">Análise completa em 5 minutos</p>
        
        <div class="info">
            ✅ Detecta erros de cobrança<br>
            ✅ Análise detalhada do seu sistema<br>
            ✅ Relatório profissional em PDF<br>
            ✅ Suporte técnico incluído
        </div>

        <form id="paymentForm">
            <div class="form-group">
                <label>Nome *</label>
                <input type="text" name="nome" required placeholder="Seu nome completo">
            </div>
            
            <div class="form-group">
                <label>Email *</label>
                <input type="email" name="email" required placeholder="seu@email.com">
            </div>
            
            <div class="form-group">
                <label>Telefone WhatsApp *</label>
                <input type="tel" name="telefone" required placeholder="62 9 9999-9999">
            </div>

            <div class="price">R$ 10,00</div>

            <button type="submit">Pagar com PIX</button>
        </form>
    </div>

    <script>
        document.getElementById('paymentForm').addEventListener('submit', async (e) => {
            e.preventDefault();
            
            const nome = document.querySelector('input[name="nome"]').value;
            const email = document.querySelector('input[name="email"]').value;
            const telefone = document.querySelector('input[name="telefone"]').value;
            
            // Simula pagamento (na prática, integrar com Mercado Pago)
            alert('Redirecionando para PIX...\\n\\nNome: ' + nome + '\\nEmail: ' + email + '\\nTelefone: ' + telefone);
        });
    </script>
</body>
</html>"""

def send_twilio_whatsapp(message):
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
            print(f"   ✅ WhatsApp enviado!")
            return True
        else:
            print(f"   ⚠️ Erro Twilio: {response.status_code}")
            return False
    except Exception as e:
        print(f"   ❌ Erro: {e}")
        return False

class RequestHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        pass
    
    def do_GET(self):
        if self.path == '/' or self.path == '/index.html':
            self.send_response(200)
            self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_LANDING.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()
    
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
            
            print(f"\n{'='*60}")
            print(f"💳 PAGAMENTO: {payment_id}")
            print(f"{'='*60}")
            
            headers = {"Authorization": f"Bearer {MERCADOPAGO_TOKEN}"}
            response = requests.get(
                f"https://api.mercadopago.com/v1/payments/{payment_id}",
                headers=headers,
                timeout=10
            )
            
            if response.status_code != 200:
                print(f"❌ Erro ao buscar pagamento")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "error"}).encode())
                return
            
            payment = response.json()
            if payment.get('status') != 'approved':
                print(f"⚠️ Pagamento não aprovado")
                self.send_response(200)
                self.end_headers()
                self.wfile.write(json.dumps({"status": "pending"}).encode())
                return
            
            print(f"✅ PAGAMENTO APROVADO\n")
            
            metadata = payment.get('metadata', {})
            nome = metadata.get('nome', 'Cliente')
            email = metadata.get('email', '')
            
            # WhatsApp
            print(f"📱 ENVIANDO WHATSAPP...")
            whatsapp_msg = f"🎉 Pagamento recebido!\n\nOlá {nome},\n\nSua análise será gerada em segundos.\nAcompanhe seu email: {email}\n\nRedesum ☀️"
            send_twilio_whatsapp(whatsapp_msg)
            
            # PDF
            print(f"📊 GERANDO ANÁLISE...")
            subprocess.Popen(
                ["python3", "/data/.openclaw/workspace/analista_faturas_bot.py", 
                 "--payment-id", str(payment_id)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            
            # Email
            if email:
                print(f"📧 ENVIANDO EMAIL...")
                time.sleep(3)
                pdfs = glob.glob(f"/data/.openclaw/workspace/analise_fatura_*.pdf")
                if pdfs:
                    pdf_path = pdfs[-1]
                    cmd = f'''bash -c '. ~/.bashrc && gog mail send --to "{email}" --subject "Análise de Fatura Solar - Redesum" --body "Olá {nome},\\n\\nSegue em anexo a análise completa de sua fatura solar.\\n\\nQualquer dúvida, estamos à disposição!\\n\\nRedesum Manutenção Usina Solar\\n+55 62 99466-6353" --attach "{pdf_path}" --account rogerio@redesun.com.br' '''
                    result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
                    if result.returncode == 0:
                        print(f"   ✅ Email enviado!")
            
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
    print("🚀 LANDING PAGE + WEBHOOK - REDESUM")
    print("="*60)
    print(f"📍 URL: http://0.0.0.0:{port}")
    print("✅ GET / → Landing page (formulário)")
    print("✅ POST /api/webhook → Processa pagamentos")
    print("="*60 + "\n")
    
    server = HTTPServer(('0.0.0.0', port), RequestHandler)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n⛔ Servidor parado")

if __name__ == "__main__":
    main()
