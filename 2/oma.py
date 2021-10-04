# -*- coding: utf-8 -*-
import cgitb
# -*- coding: utf-8 -*-
cgitb.enable()
from flask import Flask, request, Response, render_template, redirect, url_for
from jinja2 import Environment
from flask_wtf_polyglot import PolyglotForm
from wtforms import Form, StringField, validators, IntegerField, widgets
from wtforms.widgets.html5 import NumberInput
import urllib.request
import drawSvg as draw
import simplejson
import os
import requests

print("""Content-type: text/html; charset=UTF-8\n""")

app = Flask(__name__)
app.secret_key = '"s4l41n3n'

def svg(data):
    a = draw.Drawing(200, 100, origin='center', displayInline=False)
    a.append(draw.Circle(0, 0, 100,
            fill=data["basecolor"]))
    a.saveSvg('./static/images/basecolor.svg')
    b = draw.Drawing(200, 100, origin='center', displayInline=False)
    b.append(draw.Circle(0, 0, 100,
            fill=data["selectedcolor"]))
    b.saveSvg('./static/images/selectedcolor.svg')
    c = draw.Drawing(200, 100, origin='center', displayInline=False)
    c.append(draw.Circle(0, 0, 100,
            fill=data["movedcolor"]))
    c.saveSvg('./static/images/movedcolor.svg')       
    d = draw.Drawing(200, 100, origin='center', displayInline=False)
    d.append(draw.Circle(0, 0, 100,
            fill="red"))
    d.saveSvg('./static/images/red.svg')


    return


# @app.route määrää mille osoitteille tämä funktio suoritetaan
@app.route('/', methods=["GET"])
def wtlomake():
    #pelilaudan asetuksien hakeminen
    with urllib.request.urlopen("https://europe-west1-ties4080.cloudfunctions.net/vt2_taso1") as response:
        data = simplejson.load(response)
   
    #svg-kuvien luominen asetusen perusteella
    dvg = svg(data)
   
    #lomakkeen luominen
    class Form(PolyglotForm):
        x           = IntegerField(u'Laudan koko', widget=NumberInput(), default=data["min"], validators=[validators.NumberRange(min=data["min"], max=data["max"], message=u"Syötä arvo väliltä {0} - {1}".format(data["min"], data["max"]))])
        pelaaja1    = StringField(u'Pelaaja 1', validators=[validators.Length(min=1, message=u"Syöttämäsi arvo ei kelpaa")])
        pelaaja2    = StringField(u'Pelaaja 2', validators=[validators.Length(min=1, message=u"Syöttämäsi arvo ei kelpaa")])
    form = Form(request.args)
    
    #pelilaudan tilasta kertuvat argumentit
    button = request.args.get(u"XY")
    laudalla = set(request.args.getlist(u"B"))
    url = request.args.get(u"undo")
    palautettava = request.args.get(u"palautettava")
    clicked = request.args.get(u"clicked")
    tila = request.args.get(u"tila")
    vanha = request.args.get(u"old")
    vaihto = request.args.get(u"vaihto")
    pelaaja1 = request.args.get(u"pelaaja1")
    pelaaja2 = request.args.get(u"pelaaja2")  
    pelaajat = [pelaaja1,pelaaja2]
    moved = None
    #linkkien argumenttien luonti
    siirto = urllib.parse.urlencode( { u"tila": "siirto", u"vaihto": "vaihto"} )
    poisto = urllib.parse.urlencode( { u"tila": "poisto", u"vaihto": "vaihto"} )
    try:
        #luodaan siirto ja poistotiloille linkit, argumentien avulla saadaan tilasta
        siirtoUrl = request.base_url + "?" + siirto + "&" + request.full_path[2:]
        poistoUrl = request.base_url + "?" + poisto + "&" + request.full_path[2:] 
    except:
        siirtoUrl = request.base_url + "?" + siirto
        poistoUrl = request.base_url + "?" + poisto   
    try:
        #luodaan linkki siirron kumoamiselle
        args = urllib.parse.urlencode( { u"clicked": None, u"palautettava" : button } )
        kumoaUrl = request.base_url + "?" + args + "&" + url[2:]  
        
        #args = urllib.parse.urlencode( { u"clicked": "None", u"palautettava" : button } )
        #linkki = request.url.split("undo")
        #linkki = linkki[0] + args

        
    except:
        kumoaUrl = request.base_url
    #lisätään linkit taulukkoon 
    urls = [siirtoUrl,poistoUrl,kumoaUrl]
  
    # Jos pelilaudan tilaa vaihdetaan, pidetään pelilaudan tilanne ennallaan
    if vaihto == "vaihto":
        if tila == "siirto":
            try:
                laudalla.remove(button)
            except:
                pass
                
        if tila == "poisto":
            try:
                laudalla.remove(vanha)
                laudalla.add(button)
            except:
                pass
                
    elif tila == "siirto":
        try:  
            laudalla.remove(vanha) # poistetaan vanha pelimerkki
            laudalla.add(button) # lisätään se uudelle ruudulle
            moved = button
            button = None
            clicked = "False" #tehdään kumoa-linkki näkyväksi
        except:
            pass

    elif tila == "poisto":
        laudalla.remove(button) # poistetaan pelimerkki laudalta
        if not clicked:
            clicked = "False" #tehdään kumoa-linkki näkyväksi
        else:
            clicked = None

    #pelilaudan ruutujen väritys asetusten mukaan
    balls = data[u"balls"]   
    fst = data[u"first"] 
    if (fst == u"black"):
        fst = u"black"
        sec = u"white"    
    else:
        fst = u"white"
        sec = u"black"  
    #pelilaudan koon määritys, jos syöte virheellinen 
    #(ei luku, tai ei sallituilla rajoilla)
    #luodaan mimikoon pelilauta
    try:
        x = int(form.x.data)
        if x < data["min"] or x > data["max"]:
            x = data["min"]
    except:
        x = data[u"min"] 
    #lomakkeen validointi
    if request.method == 'GET' and request.args:
        form.validate()
    
    #ei aloiteta peliä, jos pelaajien nimiä ei ole määritelty
    if len(form.pelaaja1.data) == 0 or len(form.pelaaja2.data) == 0:
        tila = "alku"
    
    return render_template("jinja.xhtml", palautettava=palautettava,  poistettu=button, clicked=clicked, urls=urls, tila = tila, laudalla=list(laudalla), form=form, fst=fst, sec=sec, balls=balls, x=x, moved=moved, pelaajat=pelaajat, mimetype="application/xhtml+xml;charset=UTF-8").encode("UTF-8")

