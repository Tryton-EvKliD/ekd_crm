# -*- coding: utf-8 -*-
#This file is part of Tryton.  The COPYRIGHT file at the top level of
#this repository contains the full copyright notices and license terms.
{
    'name': 'CRM & SRM',
    'name_ru_RU': 'Учет взаимоотношений с заказчиками и поставщиками',
    'version': '1.8.0',
    'author': 'Tiny & Dmitry Klimanov',
    'email': 'k-dmitry2@narod.ru',
    'website': 'http://www.tryton.org/',
    'description': ''' 
    ''',
    'description_ru_RU': '''Учет взаимосвязей с заказчиками и поставщиками.
    ''',
    'depends': [
        'ir',
        'res',
        'party',
    ],
    'xml': [
        'xml/crm_data.xml',
        'xml/crm_view.xml',
        'xml/party_view.xml',
    ],
    'translation': [
        'ru_RU.csv',
    ]
}
