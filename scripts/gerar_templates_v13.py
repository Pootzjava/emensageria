#!/usr/bin/env python
"""
Script para gerar templates HTML baseados nos XSDs do eSocial v1.3
"""
import os
import re
from pathlib import Path

XSD_DIR = Path("/workspace/xsd/esocial/v_S_01_03_00")
TEMPLATE_DIR = Path("/workspace/apps/esocial/templates/v_S_01_03_00")

# Mapeamento de eventos S-XXXX para nomes dos arquivos XSD
EVENTO_XSD_MAP = {
    's2190': 'evtAdmPrelim',
    's2200': 'evtAdmissao',
    's2205': 'evtAltCadastral',
    's2206': 'evtAltContratual',
    's2210': 'evtAfastTemp',
    's2220': 'evtMonit',
    's2230': 'evtAnotJud',
    's2231': 'evtExpRisco',
    's2240': 'evtComProd',
    's2298': 'evtReintegr',
    's2299': 'evtBaixa',
    's2300': 'evtTSVInicio',
    's2306': 'evtTSVAltContr',
    's2399': 'evtTSVTermino',
    's2400': 'evtCessao',
    's2405': 'evtCdBenefIn',
    's2410': 'evtBenPrRP',
    's2416': 'evtCdBenefAlt',
    's2418': 'evtCdBenIn',
    's2420': 'evtCdBenAlt',
    's2500': 'evtCdBenTerm',
    's2501': 'evtReativBen',
    's3000': 'evtExclusao',
    's3500': 'evtConsolidContProc',
    's5001': 'evtInfoEmpregador',
    's5002': 'evtTabEstab',
    's5003': 'evtTabLotacao',
    's5011': 'evtTabRubrica',
    's5012': 'evtTabProcesso',
    's5501': 'evtBasesTrab',
    's5503': 'evtBasesFGTS',
    's8200': 'evtRemun',
    's8299': 'evtPgtos',
}

def extract_fields_from_xsd(xsd_file):
    """Extrai campos principais de um arquivo XSD"""
    fields = []
    try:
        with open(xsd_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        # Extrair elementos simples com anotações
        pattern = r'<xs:element name="([^"]+)"'
        matches = re.findall(pattern, content)
        
        for field_name in matches[:30]:
            if not field_name.startswith('ide') and field_name not in ['eSocial']:
                fields.append(field_name)
                
        return list(dict.fromkeys(fields))
    except Exception as e:
        print(f"Erro ao processar {xsd_file}: {e}")
        return []

def generate_template(evento_code, xsd_name, fields):
    """Gera template HTML para um evento"""
    evento_desc = xsd_name.replace('evt', '').replace('_', ' ').title()
    
    template = f'''{{% extends "esocial/base.html" %}}
{{% load static %}}

{{% block title %}}{evento_code.upper()} - {evento_desc} (v1.3){{% endblock %}}

{{% block content %}}
<div class="container">
    <h1>{evento_code.upper()} - {evento_desc}</h1>
    <p>Versão do Layout: v_S_01_03_00</p>
    
    <form method="post" action="{{% url 'esocial:enviar_evento' %}}">
        {{% csrf_token %}}
        
        <fieldset>
            <legend>Identificação do Evento</legend>
            <div class="form-group">
                <label for="tpAmb">Tipo de Ambiente:</label>
                <select name="tpAmb" id="tpAmb" required>
                    <option value="">Selecione...</option>
                    <option value="1">Produção</option>
                    <option value="2">Produção Restrita</option>
                </select>
            </div>
            <div class="form-group">
                <label for="procEmi">Processo de Emissão:</label>
                <select name="procEmi" id="procEmi" required>
                    <option value="">Selecione...</option>
                    <option value="1">Aplicativo do empregador</option>
                    <option value="2">Aplicativo governamental - Doméstico</option>
                    <option value="3">Aplicativo governamental - Web Geral</option>
                    <option value="4">Aplicativo governamental - Simplificado Pessoa Jurídica</option>
                    <option value="5">Aplicativo governamental - Segurado Especial</option>
                </select>
            </div>
            <div class="form-group">
                <label for="verProc">Versão do Processo:</label>
                <input type="text" name="verProc" id="verProc" value="1.3.0" required>
            </div>
        </fieldset>

        <fieldset>
            <legend>Identificação do Empregador</legend>
            <div class="form-group">
                <label for="tpInsc">Tipo de Inscrição:</label>
                <select name="tpInsc" id="tpInsc" required>
                    <option value="">Selecione...</option>
                    <option value="1">CNPJ</option>
                    <option value="2">CPF</option>
                </select>
            </div>
            <div class="form-group">
                <label for="nrInsc">Número de Inscrição:</label>
                <input type="text" name="nrInsc" id="nrInsc" required maxlength="14">
            </div>
        </fieldset>

        <fieldset>
            <legend>Informações do Evento</legend>
'''
    
    for field in fields[:15]:
        field_label = field.replace('_', ' ').title()
        template += f'''            <div class="form-group">
                <label for="{field}">{field_label}:</label>
                <input type="text" name="{field}" id="{field}">
            </div>
'''
    
    template += '''        </fieldset>

        <div class="form-actions">
            <button type="submit" class="btn btn-primary">Gerar XML</button>
            <button type="reset" class="btn btn-secondary">Limpar</button>
        </div>
    </form>
</div>
{% endblock %}
'''
    return template

def main():
    print("Gerando templates para eSocial v1.3...")
    
    created = 0
    for evento_code, xsd_name in EVENTO_XSD_MAP.items():
        template_file = TEMPLATE_DIR / f"{evento_code}.html"
        
        if template_file.exists():
            print(f"[SKIP] {evento_code} já existe")
            continue
            
        xsd_file = XSD_DIR / f"{xsd_name}.xsd"
        if not xsd_file.exists():
            print(f"[WARN] XSD não encontrado: {xsd_file}")
            continue
        
        fields = extract_fields_from_xsd(xsd_file)
        template_content = generate_template(evento_code, xsd_name, fields)
        
        with open(template_file, 'w', encoding='utf-8') as f:
            f.write(template_content)
        
        created += 1
        print(f"[OK] {evento_code} criado")
    
    print(f"\nTotal de templates criados: {created}")

if __name__ == "__main__":
    main()
