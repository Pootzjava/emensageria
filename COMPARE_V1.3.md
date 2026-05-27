# Comparação eSocial v1.2 → v1.3

## Resumo da Atualização

### ✅ Concluído:
1. **XSDs Oficiais v1.3 Baixados**: 52 arquivos XSD oficiais do governo
2. **Configurações Atualizadas**: 
   - `choices.py`: versão `v_S_01_03_00` adicionada e definida como default
   - `settings.py`: versão incluída na lista VERSOES_ESOCIAL
   - `.env_example`: atualizado para v1.3

3. **Estrutura de Arquivos**:
   - `/workspace/xsd/esocial/v_S_01_03_00/`: 52 XSDs oficiais
   - `/workspace/apps/esocial/templates/v_S_01_03_00/`: 48 templates HTML existentes

### 📊 Análise dos XSDs v1.3:

**Eventos Principais (já possuem templates):**
- s1000 (evtInfoEmpregador): 40 elementos
- s1005 (evtTabEstab): 42 elementos
- s1010 (evtTabRubrica): 41 elementos
- s1020 (evtTabLotacao): 37 elementos
- s1070 (evtTabProcesso): 30 elementos
- s2200 (evtAdmissao): 117 elementos
- s2205 (evtAltCadastral): 42 elementos
- s2206 (evtAltContratual): 44 elementos
- s2210 (evtAfastTemp/CAT): 33-58 elementos
- s2299 (evtDeslig): 77 elementos
- s2298 (evtReintegr): 11 elementos
- s2300 (evtTSVInicio): 88 elementos
- s2306 (evtTSVTermino): 42 elementos

**Novos Eventos na v1.3 (precisam de templates):**
- evtAdmPrelim (admissão preliminar)
- evtAnotJud (anotação judicial)
- evtBaixa
- evtBasesFGTS
- evtBasesTrab
- evtBenPrRP
- evtCS (contribuição sindical)
- evtCdBenAlt/BenIn/BenTerm (benefícios)
- evtCdBenefAlt/BenefIn
- evtCessao
- evtComProd (comercialização de produção)
- evtConsolidContProc
- evtContProc
- evtContratAvNP
- evtExcProcTrab
- evtExclusao
- evtExpRisco (exposição a risco)
- evtFGTS
- evtFGTSProcTrab
- evtFechaEvPer (fechamento)
- evtInfoComplPer
- evtIrrf/IrrfBenef
- evtMonit (monitoramento)
- evtPgtos (pagamentos)
- evtProcTrab
- evtReabreEvPer
- evtReativBen
- evtRemun (remuneração)
- evtRmnRPPS
- evtToxic (exame toxicológico)
- evtTribProcTrab

### 🔍 Mudanças Importantes na v1.3:

1. **Novos campos em eventos existentes**
2. **Novas regras de validação**
3. **Novos tipos de eventos periódicos**
4. **Alterações na estrutura de tributação**

### 📋 Próximos Passos Recomendados:

1. **Criar templates para novos eventos** (listados acima)
2. **Comparar campo a campo** os eventos existentes entre v1.2 e v1.3
3. **Atualizar models Django** se necessário
4. **Testar validação XML** contra XSDs oficiais
5. **Implementar migração de dados** se houver eventos cadastrados

## Comandos Úteis:

```bash
# Validar XML contra XSD
xmllint --noout --schema xsd/esocial/v_S_01_03_00/evtInfoEmpregador.xsd arquivo.xml

# Listar diferenças entre versões
diff -r xsd/esocial/v_S_01_02_00/ xsd/esocial/v_S_01_03_00/
```
