# Guia de Atualização para Python 3.12/3.13

Este guia detalha os passos necessários para atualizar o projeto eSocial Enterprise da versão atual do Python para as versões mais recentes (3.12 ou 3.13).

## ⚠️ Por que atualizar?

- **Performance:** Python 3.12+ traz melhorias de velocidade de 10-20% em operações gerais.
- **Segurança:** Correções de vulnerabilidades em bibliotecas padrão.
- **Sintaxe Moderna:** F-strings mais flexíveis, tipagem avançada.
- **Suporte LTS:** Versões antigas perdem suporte de segurança.

## 📋 Pré-requisitos

Antes de iniciar, verifique:
1. Backup completo do banco de dados.
2. Ambiente de Staging idêntico à Produção.
3. Todas as testes passando na versão atual.

## 🚀 Passo a Passo da Atualização

### 1. Verificação de Compatibilidade das Dependências

Algumas bibliotecas nativas (C extensions) podem precisar de recompilação ou atualização.

**Bibliotecas Críticas a Verificar:**
- `lxml`: Versão 4.9+ necessária para Python 3.12.
- `cryptography`: Versão 42+ recomendada.
- `psycopg2`: Use `psycopg2-binary` ou compile o `psycopg2` contra as libs do Python 3.12.
- `signxml`: Pode exigir ajustes devido a mudanças no `xml.etree`.

**Comando de Verificação:**
```bash
pip install pip-review
pip-review --local --auto
```

### 2. Atualização do Ambiente

#### Opção A: Usando Docker (Recomendado)
Edite seu `Dockerfile`:
```dockerfile
# De:
FROM python:3.10-slim

# Para:
FROM python:3.12-slim
```
E reconstrua:
```bash
docker-compose build --no-cache
```

#### Opção B: Usando Pyenv
```bash
pyenv install 3.12.0
pyenv local 3.12.0
python -m venv venv
source venv/bin/activate
```

### 3. Recompilação de Dependências Nativas

Após mudar a versão do Python, é obrigatório reinstalar pacotes com componentes C:

```bash
# Limpar cache
pip cache purge

# Reinstalar tudo do zero
pip install --no-cache-dir --force-reinstall -r requirements.txt
```

### 4. Ajustes de Código (Breaking Changes)

O script de automação `scripts/fix_python_version.py` (criado abaixo) ajuda a identificar problemas comuns.

**Principais Mudanças no Python 3.12/3.13:**
- **Remoção de `distutils`:** Se algum código usar `from distutils import ...`, substitua por `setuptools` ou `packaging`.
- **F-strings:** Agora permitem aninhamento de aspas sem escape, mas expresões complexas podem precisar de ajuste.
- **`datetime`:** O parâmetro `tzinfo` agora é estritamente validado.
- **`unittest`:** Algumas classes foram movidas ou depreciadas.

### 5. Execução da Suite de Testes

Rode os testes de conformidade e unitários:

```bash
# Testes Unitários
python manage.py test

# Testes de Conformidade eSocial
python manage.py runscript compliance_tests

# Validação de XMLs gerados
python manage.py runscript dry_run --check-only
```

### 6. Validação em Homologação do eSocial

Após atualizar, gere um lote de teste e envie para o ambiente de **Produção Restrita** do eSocial para garantir que a assinatura e o XML estão válidos.

## 🛠️ Script de Automação de Migração

Criei o script `scripts/migrate_python_version.py` para auxiliar neste processo.

**Uso:**
```bash
# Apenas verifica compatibilidade
python scripts/migrate_python_version.py --check

# Aplica correções automáticas de código (safe fixes)
python scripts/migrate_python_version.py --fix

# Gera relatório detalhado de incompatibilidades
python scripts/migrate_python_version.py --report
```

## 📊 Matriz de Compatibilidade Estimada

| Biblioteca | Versão Mínima | Status Python 3.12 | Status Python 3.13 |
|------------|---------------|--------------------|--------------------|
| Django     | 4.2           | ✅ Compatível       | ✅ Compatível       |
| lxml       | 4.9.0         | ✅ Compatível       | ⚠️ Testar (4.9.4+)  |
| cryptography | 42.0.0      | ✅ Compatível       | ✅ Compatível       |
| Celery     | 5.3.0         | ✅ Compatível       | ✅ Compatível       |
| psycopg2   | 2.9.9         | ✅ Compatível       | ⚠️ Preferir psycopg3|
| signxml    | 3.1.0         | ⚠️ Validar          | ❓ Aguardar update  |

## 🆘 Rollback

Se algo der errado:
1. Reverta o `Dockerfile` ou versão do `pyenv`.
2. Restaure o `requirements.txt` do backup.
3. Rode `git revert` no último commit de atualização.

---

**Nota:** A atualização para Python 3.13 é considerada "bleeding edge". Para ambientes de missão crítica como eSocial, recomenda-se estabilizar primeiro no Python 3.12 (LTS mentalmente, embora o ciclo seja anual) antes de pular para 3.13.
