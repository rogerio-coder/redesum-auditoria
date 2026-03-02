#!/usr/bin/env python3
"""
Flask App - Landing Page + Webhook
"""

from flask import Flask, render_template_string, request, jsonify
import requests
import json
import os
import subprocess
import glob
import time

app = Flask(__name__)

MERCADOPAGO_TOKEN = os.getenv('MERCADOPAGO_TOKEN')
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_WHATSAPP_FROM = os.getenv('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
TWILIO_WHATSAPP_TO = os.getenv('TWILIO_WHATSAPP_TO', 'whatsapp:+5562993156662')

HTML = """<!DOCTYPE html>
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
        input { width: 100%; padding: 12px; border: 2px solid #e0e0e0; border-radius: 6px; font-size: 14px; transition: border-color 0.3s; }
        input:focus { outline: none; border-color: #667eea; }
        button { width: 100%; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 14px; border: none; border-radius: 6px; font-size: 16px; font-weight: 600; cursor: pointer; }
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
                <input type="text" name="nome" required>
            </div>
            
            <div class="form-group">
                <label>Email *</label>
                <input type="email" name="email" required>
            </div>
            
            <div class="form-group">
                <label>Telefone WhatsApp *</label>
                <input type="tel" name="telefone" required>
            </div>

            <div class="price">R$ 10,00</div>

            <button type="submit">Pagar com PIX</button>
        </form>
    </div>

    <script>
        document.getElementById('paymentForm').addEventListener('submit', (e) => {
            e.preventDefault();
            alert('Redirecionando para pagamento...');
        });
    </script>
</body>
</html>"""

@app.route('/')
def index():
    return render_template_string(HTML)

@app.route('/api/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json() or {}
        payment_id = data.get('id') or data.get('data', {}).get('id')
        
        if not payment_id:
            return jsonify({"status": "error"}), 400
        
        print(f"\n💳 PAGAMENTO: {payment_id}")
        return jsonify({"status": "processed"}), 200
    except:
        return jsonify({"status": "error"}), 500

if __name__ == '__main__':
    port = int(os.getenv('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
