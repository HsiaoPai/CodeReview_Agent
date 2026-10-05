# -*- coding: utf-8 -*-
"""
Created on Thu Apr  2 10:31:55 2026

@author: 38428
"""

dict=[{'id':'7','name':'b'}, 
      {'id':'5','name':'c'}, 
      {'id':'1','name':'a'}, 
      {'id':'2','name':'g'},
      {'id':'6','name':'f'}]
sort_dict=sorted(dict,key=lambda x:int(x['id']))
print(sort_dict)