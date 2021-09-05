# -*- coding: utf-8 -*-

import cgitb
cgitb.enable()
from flask import Flask, request, Response, render_template
from jinja2 import Environment
from flask_wtf_polyglot import PolyglotForm
from wtforms import Form, BooleanField, StringField, validators, IntegerField, SelectField, widgets, SelectMultipleField, ValidationError
from wtforms.widgets.html5 import NumberInput
import urllib.request
import simplejson
import os
import requests

print("""Content-type: text/html; charset=UTF-8\n""")

app = Flask(__name__)
app.secret_key = '"s4l41n3n'


# @app.route määrää mille osoitteille tämä funktio suoritetaan
@app.route('/', methods=["GET"])
def wtlomake():
    with urllib.request.urlopen("https://europe-west1-ties4080.cloudfunctions.net/vt2_taso1") as response:
        data = simplejson.load(response)
   
    class Form(PolyglotForm):
        x           = IntegerField(u'Laudan koko', widget=NumberInput(), default=data["min"], validators=[validators.InputRequired(),validators.NumberRange(min=data["min"], max=data["max"], message=u"Syöttämäsi arvo ei kelpaa")])
        pelaaja1    = StringField(u'Pelaaja 1', validators=[validators.InputRequired()])
        pelaaja2    = StringField(u'Pelaaja 2', validators=[validators.InputRequired()])
    form = Form()
    
    player1 = request.args.get(u"pelaaja1")
    player2 = request.args.get(u"pelaaja2")
    poistettu = request.args.get(u"XY")
    laudalla = request.args.getlist(u"laudalla")
    url = request.args.get(u"undo")
    clicked = request.args.getlist(u"clicked")
    
    if (player1 == None and player2 == None):
        player1 = u"Pelaaja 1"
        player2 = u"Pelaaja 2"
    try:

        url = request.base_url + "?clicked=True&" + url[2:]
    except:
        url = request.base_url

    if (poistettu in laudalla):
        laudalla.remove(poistettu)
        
    balls = data[u"balls"]         
    first = data[u"first"] 

    if (first == u"black"):
        first = u"black"
        second = u"white"    
    else:
        first = u"white"
        second = u"black"    
 
    try:
        x = int(request.args.get(u"x"))
    except:
        x = data[u"min"] 
 
    if request.method == 'GET':
        form.validate()
    return render_template("jinja.xhtml", clicked=clicked, kumoa=url, poistettu=poistettu, laudalla=laudalla, x=x, form=form, pelaaja1=player1, pelaaja2=player2, first=first, second=second, balls=balls, mimetype="application/xhtml+xml;charset=UTF-8").encode("UTF-8")


#Ongelmia:
# - tarkistukset ja virheilmoitukset
# - muista lomakkeen accept-charset-ominaisuus 
# - pelaajien nimien dekoodaus