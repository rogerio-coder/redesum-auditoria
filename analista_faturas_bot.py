#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ANALISTA DE FATURAS BOT - Template Profissional
Para: Redesum Manutenção Usina Solar
Versão: 2.0

Este script:
1. Extrai texto de PDFs de faturas
2. Analisa componentes (consumo, geração, tarifas, impostos)
3. Identifica cobranças indevidas
4. Gera relatórios PDF formatados para clientes
5. Faz upload automático para Google Drive
"""

import subprocess
import re
import sys
import os
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, Image
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT, TA_JUSTIFY


class AnalistaDeFaturas:
    """
    Classe principal para análise de faturas de energia
    """
    
    def __init__(self, pdf_path, ticket_id: str | None = None):
        self.pdf_path = pdf_path
        self.ticket_id = ticket_id
        self.texto_fatura = ""
        self.dados_extraidos = {}
        self.alertas = []
        self.recomendacoes = []
    
    def extrair_texto_pdf(self):
        """Extrai texto do PDF usando pdftotext"""
        try:
            result = subprocess.run(
                ['/home/linuxbrew/.linuxbrew/bin/pdftotext', self.pdf_path, '-'],
                capture_output=True,
                text=True,
                check=True
            )
            self.texto_fatura = result.stdout
            print("✅ Texto extraído com sucesso")
            return True
        except Exception as e:
            print(f"❌ Erro ao extrair texto: {e}")
            return False
    
    def extrair_dados_basicos(self):
        """Extrai dados básicos da fatura"""
        texto = self.texto_fatura
        
        # UC (Unidade Consumidora)
        uc_match = re.search(r'(\d{10,12})', texto)
        if uc_match:
            self.dados_extraidos['uc'] = uc_match.group(1)
        
        # CNPJ/CPF
        cnpj_match = re.search(r'CNPJ/CPF:\s*([\d\.\/\-]+)', texto)
        if cnpj_match:
            self.dados_extraidos['cnpj'] = cnpj_match.group(1)
        
        # Cliente (nome)
        # Procura por linhas antes do CNPJ
        linhas = texto.split('\n')
        for i, linha in enumerate(linhas):
            if 'CNPJ/CPF:' in linha and i > 0:
                # Nome geralmente está na linha anterior
                self.dados_extraidos['cliente'] = linhas[i-1].strip()
                break
        
        # Período de referência
        periodo_match = re.search(r'(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)/(\d{4})', texto)
        if periodo_match:
            self.dados_extraidos['periodo'] = f"{periodo_match.group(1)}/{periodo_match.group(2)}"
        
        # Vencimento
        venc_match = re.search(r'(\d{2}/\d{2}/\d{4})', texto)
        if venc_match:
            self.dados_extraidos['vencimento'] = venc_match.group(1)
        
        # Valor total
        valor_match = re.search(r'R\$[\*\s]*(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
        if valor_match:
            self.dados_extraidos['valor_total'] = valor_match.group(1)
        
        # Classificação tarifária
        if 'GRUPO A' in texto.upper() or 'OPTANTE' in texto.upper():
            self.dados_extraidos['grupo_tarifario'] = 'Grupo A'
        elif 'GRUPO B' in texto.upper():
            self.dados_extraidos['grupo_tarifario'] = 'Grupo B'
        
        print(f"✅ Dados básicos extraídos: {len(self.dados_extraidos)} campos")
    
    def analisar_consumo_e_geracao(self):
        """Analisa consumo de energia e geração solar"""
        texto = self.texto_fatura
        
        # Consumo por modalidade horária
        consumos = {
            'ponta': 0,
            'fora_ponta': 0,
            'horario_reservado': 0,
            'total': 0
        }
        
        # Procura por padrões de consumo
        # Exemplo: "CONSUMO P SCEE    kWh    1300,53"
        consumo_p_match = re.search(r'CONSUMO.*?P.*?(\d{1,5}[,\.]\d{1,2})', texto)
        if consumo_p_match:
            consumos['ponta'] = float(consumo_p_match.group(1).replace(',', '.'))
        
        consumo_fp_match = re.search(r'CONSUMO.*?FP.*?(\d{1,5}[,\.]\d{1,2})', texto)
        if consumo_fp_match:
            consumos['fora_ponta'] = float(consumo_fp_match.group(1).replace(',', '.'))
        
        consumo_hr_match = re.search(r'CONSUMO.*?HR.*?(\d{1,5}[,\.]\d{1,2})', texto)
        if consumo_hr_match:
            consumos['horario_reservado'] = float(consumo_hr_match.group(1).replace(',', '.'))
        
        consumos['total'] = consumos['ponta'] + consumos['fora_ponta'] + consumos['horario_reservado']
        
        self.dados_extraidos['consumo'] = consumos
        
        # Geração solar
        geracao_match = re.search(r'INJEÇÃO.*?(\d{1,5}[,\.]\d{1,2})', texto)
        if geracao_match:
            geracao = float(geracao_match.group(1).replace(',', '.'))
            self.dados_extraidos['geracao_solar'] = geracao
            
            # Calcula percentual de compensação
            if consumos['total'] > 0:
                percentual = (geracao / consumos['total']) * 100
                self.dados_extraidos['percentual_compensacao'] = round(percentual, 1)
        
        # Créditos SCEE
        credito_match = re.search(r'CRÉDITO RECEBIDO KWH\s*(\d{1,5}[,\.]\d{1,2})', texto)
        if credito_match:
            self.dados_extraidos['credito_recebido'] = float(credito_match.group(1).replace(',', '.'))
        
        saldo_match = re.search(r'SALDO KWH:.*?FP=(\d{1,5}[,\.]\d{1,2})', texto)
        if saldo_match:
            self.dados_extraidos['saldo_creditos'] = float(saldo_match.group(1).replace(',', '.'))
        
        print(f"✅ Análise de consumo concluída: {consumos['total']:.2f} kWh consumidos")
    
    def identificar_cobranças_indevidas(self):
        """Identifica possíveis cobranças indevidas"""
        texto = self.texto_fatura
        
        # 1. FATURAMENTO USO INJEÇÃO (TUSD sobre injeção)
        tusd_injec_match = re.search(r'FATURAMENTO USO INJEÇÃO.*?(\d{1,4}[,\.]\d{2})', texto)
        if tusd_injec_match:
            valor_tusd = float(tusd_injec_match.group(1).replace(',', '.'))
            if valor_tusd > 0:
                self.alertas.append({
                    'tipo': 'cobranca_questionavel',
                    'titulo': '⚠️ Faturamento Uso Injeção',
                    'valor': f'R$ {valor_tusd:.2f}',
                    'descricao': f'Cobrança de R$ {valor_tusd:.2f} por TUSD Demanda sobre injeção solar.',
                    'justificativa': 'Pode ser indevida se o sistema foi instalado ANTES de 07/01/2023 (Lei 14.300/2022).',
                    'acao': 'Verificar data de homologação do sistema. Se anterior a 07/01/2023, contestar com base no Marco Legal da GD.'
                })
        
        # 2. ICMS sobre energia compensada
        if 'PROCESSO' in texto.upper() or 'JUDICIAL' in texto.upper():
            icms_match = re.search(r'controverso R\$\s*(\d{1,4}[,\.]\d{2})', texto)
            if icms_match:
                valor_icms = float(icms_match.group(1).replace(',', '.'))
                self.alertas.append({
                    'tipo': 'processo_judicial',
                    'titulo': '⚖️ ICMS sobre Compensação Solar',
                    'valor': f'R$ {valor_icms:.2f}',
                    'descricao': f'Valor em disputa judicial: R$ {valor_icms:.2f} de ICMS sobre energia compensada.',
                    'justificativa': 'A cobrança de ICMS sobre energia injetada (compensada) é questionável juridicamente.',
                    'acao': 'Acompanhar processo judicial. Jurisprudência favorável ao consumidor em vários estados.'
                })
        
        # 3. UFER (Fator de potência baixo)
        ufer_match = re.search(r'UFER.*?(\d{1,4}[,\.]\d{2})', texto)
        if ufer_match:
            valor_ufer = float(ufer_match.group(1).replace(',', '.'))
            if valor_ufer > 100:  # Threshold de alerta
                self.alertas.append({
                    'tipo': 'custo_evitavel',
                    'titulo': '💡 UFER Elevado',
                    'valor': f'R$ {valor_ufer:.2f}',
                    'descricao': f'Cobrança de R$ {valor_ufer:.2f} por baixo fator de potência (reativos).',
                    'justificativa': 'Equipamentos com baixa eficiência elétrica causam desperdício e multa.',
                    'acao': 'Instalar banco de capacitores. Economia estimada: R$ 300-500/mês. ROI: 10-18 meses.'
                })
                
                self.recomendacoes.append({
                    'prioridade': 'alta',
                    'tipo': 'investimento',
                    'titulo': 'Instalação de Banco de Capacitores',
                    'custo_estimado': 'R$ 5.000 - 8.000',
                    'economia_mensal': f'R$ {valor_ufer * 0.8:.2f}',
                    'roi_meses': 12
                })
        
        # 4. Fatura vencida
        if 'FATURA VENCIDA' in texto.upper() or 'NOTIFICAÇÃO' in texto.upper():
            debito_match = re.search(r'VALOR TOTAL:\s*R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})', texto)
            if debito_match:
                valor_debito = debito_match.group(1)
                self.alertas.append({
                    'tipo': 'urgente',
                    'titulo': '🔴 FATURA VENCIDA - RISCO DE CORTE',
                    'valor': f'R$ {valor_debito}',
                    'descricao': f'Débito anterior de R$ {valor_debito} pendente.',
                    'justificativa': 'Risco de suspensão do fornecimento de energia.',
                    'acao': 'URGENTE: Regularizar pagamento imediatamente para evitar corte.'
                })
        
        print(f"✅ Análise de cobranças concluída: {len(self.alertas)} alertas identificados")
    
    def gerar_relatorio_pdf(self, output_path):
        """Gera relatório PDF formatado (layout Redesun)."""

        # Brand
        BRAND_ORANGE = colors.HexColor('#F28C28')  # laranja
        BRAND_GRAY_DARK = colors.HexColor('#333333')
        BRAND_GRAY_LIGHT = colors.HexColor('#F2F2F2')

        logo_path = os.environ.get('REDESUM_LOGO_PATH', '').strip()
        company_name = "REDESUN MANUTENCOES E INSTALACOES ELETRICAS LTDA"
        company_cnpj = "55.772.071/0001-02"
        company_phone = "(62) 99946-6353"
        company_email = "comercial@redesun.com.br"
        company_city = "Aparecida de Goiânia - GO"
        company_ig = "instagram.com/manutencaousinasolar"

        data_analise = datetime.now().strftime("%d/%m/%Y %H:%M")
        ticket_txt = f"ID atendimento: {self.ticket_id}" if self.ticket_id else None

        def _draw_header_footer(canvas, _doc):
            canvas.saveState()

            # Header bar
            canvas.setFillColor(BRAND_GRAY_LIGHT)
            canvas.rect(_doc.leftMargin, A4[1] - 2.2*cm, _doc.width, 1.6*cm, fill=1, stroke=0)

            # Logo (if available)
            x = _doc.leftMargin + 0.2*cm
            y = A4[1] - 2.0*cm
            if logo_path and os.path.exists(logo_path):
                try:
                    canvas.drawImage(logo_path, x, y, width=3.0*cm, height=1.2*cm, mask='auto', preserveAspectRatio=True)
                except Exception:
                    pass

            # Title
            canvas.setFillColor(BRAND_GRAY_DARK)
            canvas.setFont('Helvetica-Bold', 12)
            canvas.drawString(_doc.leftMargin + 3.5*cm, A4[1] - 1.4*cm, "Análise Técnica de Fatura de Energia")

            canvas.setFont('Helvetica', 9)
            canvas.setFillColor(BRAND_ORANGE)
            canvas.drawRightString(_doc.leftMargin + _doc.width, A4[1] - 1.4*cm, f"Data/Hora: {data_analise}")
            if ticket_txt:
                canvas.setFillColor(BRAND_GRAY_DARK)
                canvas.drawRightString(_doc.leftMargin + _doc.width, A4[1] - 1.75*cm, ticket_txt)

            # Footer
            canvas.setFillColor(colors.grey)
            canvas.setFont('Helvetica', 8)
            canvas.drawString(_doc.leftMargin, 1.2*cm, f"{company_name} | CNPJ {company_cnpj} | WhatsApp {company_phone}")
            canvas.drawString(_doc.leftMargin, 0.85*cm, f"{company_email} | {company_city} | {company_ig}")
            canvas.drawRightString(_doc.leftMargin + _doc.width, 0.85*cm, f"Página {canvas.getPageNumber()}")
            canvas.setFont('Helvetica-Oblique', 7)
            canvas.drawString(_doc.leftMargin, 0.5*cm, "Relatório preliminar. Valores e hipóteses devem ser validados com documentos e regras vigentes da distribuidora/ANEEL.")

            canvas.restoreState()

        doc = SimpleDocTemplate(
            output_path,
            pagesize=A4,
            rightMargin=2*cm,
            leftMargin=2*cm,
            topMargin=2.6*cm,
            bottomMargin=2.1*cm,
        )
        
        styles = getSampleStyleSheet()
        
        # Estilos customizados
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=16,
            textColor=BRAND_GRAY_DARK,
            spaceAfter=10,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        subtitle_style = ParagraphStyle(
            'CustomSubtitle',
            parent=styles['Heading2'],
            fontSize=12,
            textColor=BRAND_ORANGE,
            spaceAfter=10,
            spaceBefore=10,
            fontName='Helvetica-Bold'
        )
        
        alert_style = ParagraphStyle(
            'Alert',
            parent=styles['Normal'],
            fontSize=10,
            textColor=colors.red,
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        normal_style = ParagraphStyle(
            'CustomNormal',
            parent=styles['Normal'],
            fontSize=10,
            spaceAfter=8,
            alignment=TA_JUSTIFY
        )
        
        story = []
        
        # Capa curta (o cabeçalho completo vai no topo de todas as páginas)
        story.append(Paragraph("Relatório de Análise de Fatura", title_style))
        story.append(Spacer(1, 0.4*cm))
        
        # 1. Dados Básicos
        story.append(Paragraph("1. IDENTIFICAÇÃO DA FATURA", subtitle_style))
        
        dados_basicos = [
            ['<b>Campo</b>', '<b>Informação</b>'],
            ['Cliente', self.dados_extraidos.get('cliente', 'N/A')],
            ['CNPJ', self.dados_extraidos.get('cnpj', 'N/A')],
            ['Unidade Consumidora', self.dados_extraidos.get('uc', 'N/A')],
            ['Período de Referência', self.dados_extraidos.get('periodo', 'N/A')],
            ['Vencimento', self.dados_extraidos.get('vencimento', 'N/A')],
            ['Grupo Tarifário', self.dados_extraidos.get('grupo_tarifario', 'N/A')],
            ['<b>VALOR TOTAL</b>', f"<b>R$ {self.dados_extraidos.get('valor_total', '0,00')}</b>"],
        ]
        
        table_dados = Table(dados_basicos, colWidths=[7*cm, 10*cm])
        table_dados.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), BRAND_GRAY_DARK),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), BRAND_GRAY_LIGHT),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
        ]))
        
        story.append(table_dados)
        story.append(Spacer(1, 0.5*cm))
        
        # 2. Alertas Críticos
        if self.alertas:
            story.append(Paragraph("2. ⚠️ ALERTAS E PONTOS DE ATENÇÃO", subtitle_style))
            
            for i, alerta in enumerate(self.alertas, 1):
                story.append(Paragraph(f"<b>{i}. {alerta['titulo']}</b> - {alerta['valor']}", alert_style))
                story.append(Paragraph(f"<i>Descrição:</i> {alerta['descricao']}", normal_style))
                story.append(Paragraph(f"<i>Justificativa:</i> {alerta['justificativa']}", normal_style))
                story.append(Paragraph(f"<i>💡 Ação Recomendada:</i> {alerta['acao']}", normal_style))
                story.append(Spacer(1, 0.3*cm))
        
        # 3. Consumo e Geração
        if 'consumo' in self.dados_extraidos:
            story.append(Paragraph("3. CONSUMO E GERAÇÃO SOLAR ☀️", subtitle_style))
            
            consumo = self.dados_extraidos['consumo']
            consumo_data = [
                ['<b>Modalidade</b>', '<b>Consumo (kWh)</b>'],
                ['Horário de Ponta', f"{consumo['ponta']:.2f}"],
                ['Fora de Ponta', f"{consumo['fora_ponta']:.2f}"],
                ['Horário Reservado', f"{consumo['horario_reservado']:.2f}"],
                ['<b>Total Consumido</b>', f"<b>{consumo['total']:.2f}</b>"],
            ]
            
            if 'geracao_solar' in self.dados_extraidos:
                consumo_data.append(['', ''])
                consumo_data.append(['Geração Solar (Injeção)', f"{self.dados_extraidos['geracao_solar']:.2f}"])
                consumo_data.append(['Percentual de Compensação', f"{self.dados_extraidos.get('percentual_compensacao', 0):.1f}%"])
            
            table_consumo = Table(consumo_data, colWidths=[10*cm, 7*cm])
            table_consumo.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), BRAND_ORANGE),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BACKGROUND', (0, 1), (-1, -1), BRAND_GRAY_LIGHT),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CCCCCC')),
                ('FONTSIZE', (0, 1), (-1, -1), 9),
            ]))
            
            story.append(table_consumo)
            story.append(Spacer(1, 0.5*cm))
        
        # 4. Recomendações
        if self.recomendacoes:
            story.append(Paragraph("4. 💡 RECOMENDAÇÕES DE ECONOMIA", subtitle_style))
            
            for i, rec in enumerate(self.recomendacoes, 1):
                story.append(Paragraph(f"<b>{i}. {rec['titulo']}</b> (Prioridade: {rec['prioridade'].upper()})", normal_style))
                story.append(Paragraph(f"Investimento estimado: {rec['custo_estimado']}", normal_style))
                story.append(Paragraph(f"Economia mensal: {rec['economia_mensal']}", normal_style))
                story.append(Paragraph(f"Retorno do investimento: ~{rec['roi_meses']} meses", normal_style))
                story.append(Spacer(1, 0.3*cm))
        
        # Assinatura / contato (também está no rodapé, mas aqui fica mais explícito no final)
        story.append(Spacer(1, 0.8*cm))
        assinatura = (
            f"<b>{company_name}</b><br/>"
            f"CNPJ: {company_cnpj}<br/>"
            f"WhatsApp: {company_phone} | Email: {company_email}<br/>"
            f"{company_city} | {company_ig}"
        )
        story.append(Paragraph(assinatura, ParagraphStyle('Ass', parent=styles['Normal'], fontSize=9, textColor=BRAND_GRAY_DARK, alignment=TA_CENTER)))

        # Gera PDF com header/rodapé em todas as páginas
        doc.build(story, onFirstPage=_draw_header_footer, onLaterPages=_draw_header_footer)
        print(f"✅ PDF gerado com sucesso: {output_path}")
        return output_path
    
    def fazer_upload_drive(self, pdf_path, nome_arquivo):
        """Faz upload do PDF para Google Drive"""
        try:
            result = subprocess.run(
                [
                    'bash', '-c',
                    f'. ~/.bashrc && gog drive upload {pdf_path} --name "{nome_arquivo}" --account rogerio@redesun.com.br'
                ],
                capture_output=True,
                text=True,
                check=True
            )
            
            # Extrai o link do resultado
            link_match = re.search(r'link\s+(https://drive\.google\.com[^\s]+)', result.stdout)
            if link_match:
                link = link_match.group(1)
                print(f"✅ Upload concluído: {link}")
                return link
            else:
                print("⚠️ Upload realizado mas link não encontrado")
                return None
        except Exception as e:
            print(f"❌ Erro ao fazer upload: {e}")
            return None
    
    def analisar(self):
        """Executa análise completa"""
        print("🔍 Iniciando análise de fatura...")
        
        if not self.extrair_texto_pdf():
            return False
        
        self.extrair_dados_basicos()
        self.analisar_consumo_e_geracao()
        self.identificar_cobranças_indevidas()
        
        print("✅ Análise concluída!")
        return True


def main():
    """Função principal"""
    import requests
    
    # Verifica se --payment-id foi passado
    if "--payment-id" in sys.argv:
        try:
            payment_id = sys.argv[sys.argv.index("--payment-id") + 1]
            print(f"🔄 Buscando pagamento {payment_id}...")
            
            # Busca o pagamento na API do Mercado Pago
            token = os.getenv('MERCADOPAGO_ACCESS_TOKEN', 'APP_USR-462417171268457-022808-e6898e6987c65a65d9b5aa3be09f12eb-3232594663')
            headers = {"Authorization": f"Bearer {token}"}
            response = requests.get(f"https://api.mercadopago.com/v1/payments/{payment_id}", headers=headers, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Erro ao buscar pagamento: {response.status_code}")
                sys.exit(1)
            
            payment = response.json()
            metadata = payment.get('metadata', {})
            
            # Tenta usar o caminho completo primeiro
            pdf_path = metadata.get('fatura_path', '')
            
            if pdf_path and os.path.exists(pdf_path):
                print(f"✅ Arquivo encontrado: {pdf_path}")
            else:
                # Fallback: procura pelo nome do arquivo
                fatura_arquivo = metadata.get('fatura_arquivo', '')
                
                # Procura pelo arquivo na pasta invoices
                import glob
                pattern = f"/data/.openclaw/workspace/invoices/*{fatura_arquivo}*"
                matching_files = glob.glob(pattern, recursive=True)
                
                if not matching_files:
                    # Tenta procurar apenas pelo nome sem extensão
                    fatura_base = fatura_arquivo.replace('.pdf', '').replace('.jpg', '').replace('.jpeg', '').replace('.png', '')
                    pattern = f"/data/.openclaw/workspace/invoices/*{fatura_base}*"
                    matching_files = glob.glob(pattern, recursive=True)
                
                if not matching_files:
                    print(f"❌ Arquivo de fatura não encontrado: {fatura_arquivo}")
                    sys.exit(1)
                
                pdf_path = matching_files[0]
                print(f"✅ Arquivo encontrado: {pdf_path}")
            
            # Usa o payment_id como ticket_id
            ticket_id = payment_id
            
        except Exception as e:
            print(f"❌ Erro ao processar --payment-id: {e}")
            sys.exit(1)
    else:
        if len(sys.argv) < 2:
            print("Uso: python3 analista_faturas_bot.py <caminho_pdf_fatura>")
            print("  ou: python3 analista_faturas_bot.py --payment-id <id>")
            sys.exit(1)
        
        pdf_path = sys.argv[1]
        ticket_id = None
        
        if "--ticket-id" in sys.argv:
            try:
                ticket_id = sys.argv[sys.argv.index("--ticket-id") + 1]
            except Exception:
                ticket_id = None

    # Cria instância do analisador
    analisador = AnalistaDeFaturas(pdf_path, ticket_id=ticket_id)
    
    # Executa análise
    if not analisador.analisar():
        print("❌ Falha na análise")
        sys.exit(1)
    
    # Gera relatório PDF
    periodo = analisador.dados_extraidos.get('periodo', 'desconhecido')
    cliente = analisador.dados_extraidos.get('cliente', 'cliente')[:30]  # Limita tamanho
    output_filename = f"analise_fatura_{cliente.replace(' ', '_')}_{periodo.replace('/', '')}.pdf"
    output_path = f"/data/.openclaw/workspace/{output_filename}"
    
    analisador.gerar_relatorio_pdf(output_path)
    
    # Upload para Drive
    nome_drive = f"Análise Fatura - {cliente} - {periodo}.pdf"
    link = analisador.fazer_upload_drive(output_path, nome_drive)
    
    if link:
        print(f"\n📄 Relatório disponível em: {link}")
    
    print("\n✅ Processo concluído!")


if __name__ == "__main__":
    main()
