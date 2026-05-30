from django.core.validators import EMPTY_VALUES
import re
from django.db import models
from django import template
import decimal
import locale

try:
    locale.setlocale(locale.LC_ALL, 'pt_BR.UTF-8')
except locale.Error:
    try:
        locale.setlocale(locale.LC_ALL, 'pt_BR.utf8')
    except locale.Error:
        # Fallback to C locale if pt_BR is not available
        locale.setlocale(locale.LC_ALL, 'C')

register = template.Library()



@register.filter('is_list')
def is_list(value):
    if type(value) is list:
        return True
    return False


@register.filter('finditem')
def finditem(obj, key):
    if isinstance(obj, dict):
        if key in obj.keys():
            return obj[key]
        else:
            for k, v in obj.items():
                if isinstance(v, dict):
                    item = finditem(v, key)
                    if item is not None:
                        return item
    elif isinstance(obj, list):
        for a in obj:
            finditem(a, key)


@register.filter('read_ocorrencias')
def read_ocorrencias(string):
    import json
    lista = []
    obj = json.loads(string or '{}')
    if isinstance(obj, list):
        for o in obj:
            lista.append({'tipo': o.get('ocorrencia').get('tipo'),
                 'codigo': o.get('ocorrencia').get('codigo'),
                 'descricao': o.get('ocorrencia').get('descricao'),
                 'localizacao': o.get('ocorrencia').get('localizacao')})
    elif isinstance(obj, dict) and isinstance(obj.get('ocorrencias'), dict) and isinstance(obj.get('ocorrencias').get('ocorrencia'), list):
        for o in obj.get('ocorrencias').get('ocorrencia'):
            lista.append({'tipo': o.get('tipo'),
                 'codigo': o.get('codigo'),
                 'descricao': o.get('descricao'),
                 'localizacao': o.get('localizacao')})
    elif isinstance(obj, dict) and isinstance(obj.get('ocorrencia'), dict):
        lista.append({'tipo': obj.get('ocorrencia').get('tipo'),
             'codigo': obj.get('ocorrencia').get('codigo'),
             'descricao': obj.get('ocorrencia').get('descricao'),
             'localizacao': obj.get('ocorrencia').get('localizacao')})
    elif isinstance(obj, dict) and isinstance(obj.get('ocorrencia'), list):
        for o in obj.get('ocorrencia'):
            lista.append({'tipo': o.get('tipo'),
                 'codigo': o.get('codigo'),
                 'descricao': o.get('descricao'),
                 'localizacao': o.get('localizacao')})
    elif isinstance(obj, dict) and isinstance(obj.get('ocorrencias'), list):
        for o in obj.get('ocorrencias'):
            lista.append({'tipo': o.get('ocorrencia').get('tipo'),
                 'codigo': o.get('ocorrencia').get('codigo'),
                 'descricao': o.get('ocorrencia').get('descricao'),
                 'localizacao': o.get('ocorrencia').get('localizacao')})
    else:
        raise Exception(obj)
    return lista


@register.filter('read_ocorrencias_lote')
def read_ocorrencias_lote(string):
    import json
    lista = []
    obj = json.loads(string or '{}')
    if isinstance(obj.get('ocorrencia'), list):
        for o in obj.get('ocorrencia'):
            lista.append({'tipo': o.get('tipo'),
                 'codigo': o.get('codigo'),
                 'descricao': o.get('descricao'),
                 'localizacao': o.get('localizacao')})
    return lista


@register.filter('get_tipo_erro')
def get_tipo_erro(string):
    # 1 - Erro
    # 2 - Advertência
    if int(string) == 1:
        return 'ERRO'
    else:
        return 'ADVERTÊNCIA'


@register.filter('to_json')
def to_json(string):
    import json
    try:
        return json.loads(string)
    except:
        return ''


@register.filter('get_form')
def get_form(obj):
    return "{}/{}.html".format(obj.versao, obj.evento)


@register.filter('disabled')
def disabled(obj):
    if not obj.is_aberto:
        return 'disabled="disabled"'
    return "" 


@register.filter('test')
def test(obj):
    try:
        print()
        print(obj.__dict__)
    except:
        pass
    return ''


@register.filter(name='readjson')
def readjson(json_string, arg):
    import json
    if not json_string:
        json_string = ''
    if not isinstance(json_string, str):
        json_string = json.dumps(json_string)
    if json_string:
        json_obj = json.loads(json_string)
        arg = "['%s']" % arg.replace(".", "']['")
        try:
            return eval('json_obj' + arg)
        except KeyError:
            return ''
    else:
        return ''



@register.filter('render_with_model_dict')
def render_with_model_dict(var, model):
    #
    # usage example {{ var|render_with_dict:model }}
    #
    if var:
        dict = model.__dict__
        return var % dict
    else:
        return ''


@register.filter('to_sql')
def to_sql(value):
    return value.replace("'", "''")


@register.filter('to_list')
def to_list(value):
    return value.split(',')


@register.filter(name='data_en_to_br')
def data_en_to_br(value):
    value = value.replace("/", "-")
    v = value.split('-')
    return v[2] + '/' + v[1] + '/' + v[0]


@register.filter(name='is_int')
def is_int(value):
    try:
        test = int(value)
        return True
    except:
        return False


@register.filter(name='multiply')
def multiply(value, arg):
    return value * arg


@register.filter(name='underline_to_hyphen')
def underline_to_hyphen(value):
    return value.replace("_", "-")


@register.filter(name='format_number_2dec_xml_reinf')
def format_number_2dec_xml_reinf(value):
    return str(value).replace('.', ',')


@register.filter(name='format_number_4dec_xml_reinf')
def format_number_4dec_xml_reinf(value):
    return str(value).replace('.', ',')


@register.filter(name='replace_aspas')
def replace_aspas(value):
    if not value:
        value = ''
    return value.replace("'", '"')


@register.filter(name='format_number_2dec_xml')
def format_number_2dec_xml(value):
    return "{:0.2f}".format(value)


@register.filter(name='format_number_4dec_xml')
def format_number_4dec_xml(value):
    return "{:0.4f}".format(value)


@register.filter(name='inteiro_xml')
def inteiro_xml(value):
    return str(int(value))


@register.filter(name='query')
def query(qs, **kwargs):
    """ template tag which allows queryset filtering. Usage:
          {% query books author=author as mybooks %}
          {% for book in mybooks %}
            ...
          {% endfor %}
    """
    return qs.filter(**kwargs)


@register.filter(name='to_xml')
def to_xml(texto):
    try:
        # texto = str(texto)
        texto = texto.replace(">", '&gt;')
        texto = texto.replace("<", '&lt;')
        texto = texto.replace("&", '&amp;')
        texto = texto.replace('"', '&quot;')
        texto = texto.replace("'", '&apos;')
    except:
        pass
    return texto



@register.filter(name='dec_to_int')
def dec_to_int(var):
    return int(var)


@register.filter(name='valor')
def valor(var):
    a = str(var).replace('.', '')
    return a


@register.filter(name='to_str')
def to_str(var):
    a = str(var)
    return a


@register.filter('json_tab')
def json_return_page(json_str, variavel):
    if json_str == '{}':
        json_str = json_str.replace('}', '"tab": "%s"}' % variavel)
    else:
        json_str = json_str.replace('}', ', "tab": "%s"}' % variavel)
    return json_str


@register.filter('json_return_page')
def json_return_page(json_str, variavel):
    if json_str == '{}':
        json_str = json_str.replace('}', '"return_page": "%s"}' % variavel)
    else:
        json_str = json_str.replace('}', ', "return_page": "%s"}' % variavel)
    return json_str


@register.filter('json_return_hash')
def json_return_hash(json_str, variavel):
    if json_str == '{}':
        json_str = json_str.replace('}', '"return_hash": "%s"}' % variavel)
    else:
        json_str = json_str.replace('}', ', "return_hash": "%s"}' % variavel)
    return json_str


@register.filter('json_id')
def json_id(json_str, variavel):
    if json_str == '{}':
        json_str = json_str.replace('}', '"id": "%s"}' % variavel)
    else:
        json_str = json_str.replace('}', ', "id": "%s"}' % variavel)
    return json_str


@register.filter('json_print')
def json_print(json_str, variavel):
    if json_str == '{}':
        json_str = json_str.replace('}', '"print": "%s"}' % variavel)
    else:
        json_str = json_str.replace('}', ', "print": "%s"}' % variavel)
    return json_str


def DV_maker(v):
    if v >= 2:
        return 11 - v
    return 0


@register.filter(name='validate_CPF')
def validate_CPF(value):
    """
    Value can be either a string in the format XXX.XXX.XXX-XX or an
    11-digit number.
    """
    value = value.replace('.', '').replace('-', '')
    if value in EMPTY_VALUES:
        return False
    if not value.isdigit():
        value = re.sub(r"[-\.]", "", value)
    orig_value = value[:]
    try:
        int(value)
    except ValueError:
        return False
    if len(value) != 11:
        return False
    orig_dv = value[-2:]

    new_1dv = sum([i * int(value[idx])
                   for idx, i in enumerate(range(10, 1, -1))])
    new_1dv = DV_maker(new_1dv % 11)
    value = value[:-2] + str(new_1dv) + value[-1]
    new_2dv = sum([i * int(value[idx])
                   for idx, i in enumerate(range(11, 1, -1))])
    new_2dv = DV_maker(new_2dv % 11)
    value = value[:-1] + str(new_2dv)
    if value[-2:] != orig_dv:
        return False
    return True


@register.filter('addstr')
def addstr(arg1, arg2):
    # concatenate arg1 & arg2
    return str(arg1) + str(arg2)


@register.filter('add')
def add(arg1, arg2):
    # concatenate arg1 & arg2
    return str(arg1) + '|' + str(arg2)


@register.filter('get_permissao')
def get_permissao(dict, key):
    # print dict[str(key)], key
    try:
        if dict[str(key)] == 0:
            return False
        if dict[str(key)] == 1:
            return True
    except:
        return False


@register.filter('divide')
def divide(value, arg):
    if not arg:
        arg = 0
    if not value:
        value = 0
    # from __future__ import division
    quant_total = (arg * 100.00)
    if int(quant_total) == 0:
        quant_total = 1
    quant_nao_enviado = (value * 100.00)
    quant_enviado = quant_total - quant_nao_enviado
    # print quant_total, quant_nao_enviado, quant_enviado
    divide = (quant_enviado / quant_total) * 100
    # print divide
    return int(divide)


# @register.filter('base64_encode_me')
# def base64_encode_me(text, obj_id):
#    url = str(text).replace('_', '-')
#    #print url
#    #print str(obj_id)
#    text = url+'|'+str(obj_id)
#    #print text
#    import base64
#    encode_to_url = base64.urlsafe_b64encode( text )
#    #print encode_to_url
#    return encode_to_url

@register.filter('base64_encode_me')
def base64_encode_me(text):
    import base64
    encode_to_url = base64.urlsafe_b64encode(text)
    return encode_to_url


@register.filter('get_value_from_dict')
def get_value_from_dict(dict_data, key):
    #
    # usage example {{ your_dict|get_value_from_dict:your_key }}
    #
    if key:
        a = dict_data.get(key)
        # print key, a
        try:
            a = int(a)
        except:
            pass
        if not a:
            a = ''
        return a


# @register.simple_tag
# def quant_eleitores_cidade(obj, conta_id):
#     quantidade = Eleitores.objects.using('default').filter(cidade=obj.id, conta=conta_id, excluido=False).all()
#     return len(quantidade)
#
# @register.simple_tag
# def quant_eleitores_partido(obj, conta_id):
#     quantidade = Eleitores.objects.using('default').filter(partido=obj.id, conta=conta_id, excluido=False).all()
#     return len(quantidade)

@register.filter(name='addcss')
def addcss(value, arg):
    return value.as_widget(attrs={'class': arg})


@register.filter(name='addcss_select2')
def addcss_select2(value, arg):
    return value.as_widget(attrs={'class': arg, 'style': 'width: 100%'})


# register = Library()


@register.filter(name='notNone')
def notNone(var):
    a = ''
    if var:
        a = var
    return a


@register.filter(name='mes_ano')
def mes_ano(var):
    mes = var[4:7]
    ano = var[2:4]
    if mes == '01':
        mes = 'Jan/'
    if mes == '02':
        mes = 'Fev/'
    if mes == '03':
        mes = 'Mar/'
    if mes == '04':
        mes = 'Abr/'
    if mes == '05':
        mes = 'Mai/'
    if mes == '06':
        mes = 'Jun/'
    if mes == '07':
        mes = 'Jul/'
    if mes == '08':
        mes = 'Ago/'
    if mes == '09':
        mes = 'Set/'
    if mes == '10':
        mes = 'Out/'
    if mes == '11':
        mes = 'Nov/'
    if mes == '12':
        mes = 'Dez/'
    return mes + ano


@register.filter(name='ano_mes_extenso')
def ano_mes_extenso(value):
    a = value.split('-')
    ano = a[0]
    mes = a[1]
    if mes == '01':
        mes_extenso = 'Janeiro'
    elif mes == '02':
        mes_extenso = 'Fevereiro'
    elif mes == '03':
        mes_extenso = 'Março'
    elif mes == '04':
        mes_extenso = 'Abril'
    elif mes == '05':
        mes_extenso = 'Maio'
    elif mes == '06':
        mes_extenso = 'Junho'
    elif mes == '07':
        mes_extenso = 'Julho'
    elif mes == '08':
        mes_extenso = 'Agosto'
    elif mes == '09':
        mes_extenso = 'Setembro'
    elif mes == '10':
        mes_extenso = 'Outubro'
    elif mes == '11':
        mes_extenso = 'Novembro'
    elif mes == '12':
        mes_extenso = 'Dezembro'
    return mes_extenso + '/' + ano


# @register.filter(name='total')
# def total(list, arg):
#     soma = sum(d[arg] for d in list)
#     soma = round(soma, 2)
#     soma = soma*1.00
#     valor = real(soma)
#     return valor

@register.filter(name='inteiro')
def inteiro(var):
    # print var
    a = str(var).split('.')
    b = a[0]
    # print b
    return int(b)


@register.filter(name='padrao_americano')
def padrao_americano(var):
    # print var
    # a = str(var).replace('.','')
    # print a
    return str(var)


@register.filter(name='total_quant')
def total_quant(list, arg):
    soma = sum(d[arg] for d in list)
    return soma


@register.filter(name='percentage')
def percentage(fraction, population):
    # {{ yes.count|percentage:votes.count }} votes.count - total ||| yes.count - parcial
    try:
        return "%.2f%%" % ((float(fraction) / float(population)) * 100)
    except ValueError:
        return ''
