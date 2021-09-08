from flask import Flask, request, make_response
from math import sin, cos, sqrt, atan2, radians
import datetime
import urllib.request
import random
import simplejson
import io

#               TASO 1              #

#Palauttaa merkkijonon jossa rastien koodit puolipisteellä eroteltuna.
#Hyväksytään vain koodit, jotka alkavat kokonaisluvulla
def rastien_koodit(data):
    mjono = []
    for a in data["rastit"]:
        try:
            int(a["koodi"][0])
            mjono.append(a["koodi"])
        except ValueError:
            pass
    return ";".join(mjono)

# Joukkuelistaus aakkosjärjestyksessä
def joukkueet_eka(data):
    joukkueet = []
    for i in data["sarjat"]:
        for j in i["joukkueet"]:
            joukkueet.append(j["nimi"])
    joukkueet.sort(key=str.casefold)
    return "\n".join(joukkueet)

# Lisää parametrina saadun joukkueen parametrina saatuun sarjaan.
# Tarkastaa myös, ettei joukkueen id ole käytössä. Jos on, generoidaan uusi. Muokatessa joukkuetta säilytetään vanha id
def lisaa_joukkue(data, sarja, joukkue, muokkaus):
    if joukkue["nimi"] == None or sarja == None:
        return None #jos joukkueelle ei löydetä nimeä tai sarjaa ei ole syötetty ei tehdä mitään
    for s in data["sarjat"]:
        for j in s["joukkueet"]:
            if j["nimi"].upper().strip() == joukkue["nimi"].upper().strip() and not muokkaus:
                return False # Jos samanniminen joukkue löytyy ei lisätä
            # Muokatessa ei saa käyttää samaa nimeä kuin toisella joukkueella
            if muokkaus and j["nimi"].upper().strip() == joukkue["nimi"].upper().strip() and  str(j["id"]).upper().strip() != str(joukkue["id"]).upper().strip():
                return False
    for d in data["sarjat"]:
        if d["nimi"].upper().strip() == sarja.upper().strip():
            if not muokkaus:
                joukkue["id"] = joukkueen_id(data) #
            joukkue["leimaustapa"] = leimaustapa(data, joukkue["leimaustapa"])
            d["joukkueet"].append(joukkue)
            return True
    return None

#Etsii leimaustapojen indeksit nimen perusteella
def leimaustapa(data, leimaustapa):
    leimaustavat = []
    for lt in data["leimaustapa"]:
        if lt in leimaustapa:
            leimaustavat.append(data["leimaustapa"].index(lt))
    return leimaustavat

#Etsii käyttämättömän id:n ja palauttaa käyttämättömän sen
def joukkueen_id(data):
    id_lista = []
    for s in data["sarjat"]:
        for j in s["joukkueet"]:
            id_lista.append(j["id"])
    while True:
        i = random.randint(1e15,1e16)
        if i not in id_lista:
            return i

#               TASO 3              #

# Poistaa parametrina saadusta sarjasta parametrina saadun joukkueen
def poista_joukkue(data, sarja, joukkue, muokkaus):
    for d in range(len(data["sarjat"])):
        if data["sarjat"][d]["nimi"].upper() == sarja.upper():
            for j in range(len(data["sarjat"][d]["joukkueet"])):
                if not muokkaus:
                    if data["sarjat"][d]["joukkueet"][j]["nimi"].upper().strip() == joukkue.upper().strip():
                        del data["sarjat"][d]["joukkueet"][j]
                        return
                if muokkaus:
                    if str(data["sarjat"][d]["joukkueet"][j]["id"]) == str(joukkue).strip():
                        del data["sarjat"][d]["joukkueet"][j]
                        return
    return

#Joukkuelistaus, jossa mukana joukkueen pisteet
def joukkueet_toka(data):
    joukkueet = []
    string = ""
    for i in data["sarjat"]:
        for j in i["joukkueet"]:
            joukkue =   {
                "jasenet": [],
                "nimi": "",
                "pisteet": 0
                }
            joukkue["nimi"] = j["nimi"]
            joukkue["jasenet"] = j["jasenet"]
            joukkue["jasenet"].sort();
            joukkue["pisteet"] = laske_pisteet(j["rastit"], data)
            joukkueet.append(joukkue)
    joukkueet.sort(key=lambda joukkue: joukkue["nimi"])
    joukkueet.sort(key=lambda joukkue: joukkue["pisteet"], reverse=True)
    for k in joukkueet:
        string += "\n{0} ({1} p) \n\t".format(k["nimi"],k["pisteet"])
        jasenet = "\n\t".join(k["jasenet"])
        string += jasenet
    return string

#Apufunktio pisteiden laskua varten
def laske_pisteet(rastit, data):
    alkuaika = datetime.datetime.strptime(data["alkuaika"], '%Y-%m-%d %H:%M:%S')
    loppuaika  = datetime.datetime.strptime(data["loppuaika"], '%Y-%m-%d %H:%M:%S')
    pisteet = 0
    kaydyt = []
    for r in rastit:
        for d in data["rastit"]:
            if str(d["id"]) == str(r["rasti"]):
                aika = datetime.datetime.strptime(r["aika"], '%Y-%m-%d %H:%M:%S')
                if aika >  alkuaika and aika < loppuaika and str(r["rasti"]) not in kaydyt:
                    try:
                        pisteet += int(d["koodi"][0])
                        kaydyt.append(str(r["rasti"]))
                    except:
                        pass
    return pisteet

#               TASO 5              #

#Joukkuelistaus, jossa mukana pisteet, kuljettu matka, sekä aika
def joukkueet_kolmas(data):
    joukkueet = []
    string = ""
    for i in data["sarjat"]:
        for j in i["joukkueet"]:
            joukkue =   {
                "jasenet": [],
                "nimi": "",
                "pisteet": 0
                }
            joukkue["nimi"] = j["nimi"]
            joukkue["jasenet"] = j["jasenet"]
            joukkue["jasenet"].sort();
            joukkue["pisteet"] = laske_pisteet(j["rastit"], data)
            joukkue["matka"] = laske_matka(j["rastit"], data)
            joukkue["aika"] = laske_aika(j["rastit"], data)
            joukkueet.append(joukkue)
    joukkueet.sort(key=lambda joukkue: joukkue["nimi"])
    joukkueet.sort(key=lambda joukkue: joukkue["pisteet"], reverse=True)
    for k in joukkueet:
        string += "\n{0} ({1} p, {2} km, 0{3})\n\t".format(k["nimi"],k["pisteet"], k["matka"], k["aika"])
        jasenet = "\n\t".join(k["jasenet"])
        string += jasenet
    return string

#Apufunktio joukkueen kulkeman matkan laskemiseen
def laske_matka(rastit, data):
    # kerätään joukkueen käymät todelliset rastit taulukkoon
    kuljetut = []
    for r in rastit:
        r1 = rasti(r["rasti"], data)
        if r1:
            kuljetut.append(r1)

    matka = 0
    lahto = False
    i = 0
    j = i + 1
    #Käydään rastit läpi ja lasketaan peräkkäisten rastien välien pituudet
    while j<len(kuljetut):
        r1 = kuljetut[i]
        r2 = kuljetut[j]
        if r1["koodi"] == "MAALI":
            break
        if r1["koodi"] == "LAHTO" or lahto:
            if (r1["koodi"] == "LAHTO"):
                matka = 0
            lahto = True
            lat1 = float(r1["lat"])
            lon1 = float(r1["lon"])
            lat2 = float(r2["lat"])
            lon2 = float(r2["lon"])
            km = etaisyys(lat1,lon1,lat2,lon2)
            if (type(km) == float):
                matka += km
            i+=1
            j+=1
    return round(matka)


#Apufunktio rastin palautukseen
def rasti(rasti, data):
    for r in data["rastit"]:
        if str(r["id"]) == str(rasti):
            return r
    return None

#Apufunktio kahden rastin etäisyyden laskemiseen
def etaisyys(a, b, c, d):
    R = 6373.0
    lat1 = radians(a)
    lon1 = radians(b)
    lat2 = radians(c)
    lon2 = radians(d)

    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    distance = R * c
    return distance

#Apufunktio joukkueen käyttämän ajan laskuun.
def laske_aika(rastit, data):
    maali_Id = None
    for a in data["rastit"]:
        if a["koodi"] == "MAALI":
            maali_Id = str(a["id"])
    lahto_Id = None
    for b in data["rastit"]:
        if b["koodi"] == "LAHTO":
            lahto_Id = str(b["id"])

    lahtoaika = None
    for c in rastit:
        if str(c["rasti"]) == lahto_Id:
            lahtoaika = datetime.datetime.strptime(c["aika"], "%Y-%m-%d %H:%M:%S")

    loppuaika = None
    for d in rastit:
        if str(d["rasti"]) == maali_Id:
            loppuaika = datetime.datetime.strptime(d["aika"], "%Y-%m-%d %H:%M:%S")
    try:
        return loppuaika - lahtoaika
    except:
        return "0:00:00"

#Päivitetään joukkue
def paivita(data, tunniste, joukkue, sarja):
    lista = list(filter(lambda d: d['nimi'] == sarja, data["sarjat"])) # tarkistetaan että sarja löytyy tietorakenteesta
    if len(lista) < 1:
        return
    i = ""
    for s in data["sarjat"]:
        for j in s["joukkueet"]:
            if str(j["id"]) == str(tunniste).strip():
                i = s["nimi"]
            if str(j["id"]) == str(tunniste) and s["nimi"].upper() == sarja.upper():
                    if lisaa_joukkue(data, sarja, joukkue, True):
                        poista_joukkue(data, sarja, tunniste, True)
            if str(j["id"]) == str(tunniste) and s["nimi"].upper() != sarja.upper():
                    if lisaa_joukkue(data, sarja, joukkue, True):
                        poista_joukkue(data, i, tunniste, True)
                    return
    return None

app = Flask(__name__)

@app.route('/')
def hello_world():
    return 'Hello from Flask!'

@app.route('/vt1')
def aloita():
    with urllib.request.urlopen("http://hazor.eu.pythonanywhere.com/2021/data.json") as response:
        data = simplejson.load(response)
    reset = request.args.get("reset")
    sarja = request.args.get("sarja")
    tila = request.args.get("tila")
    tunniste = request.args.get("id")

    nimi = request.args.get("nimi")
    jasenet = request.args.getlist("jasen")
    leimaustavat = request.args.getlist("leimaustapa")
    joukkue = {
        "nimi": nimi,
        "jasenet": jasenet,
        "id": tunniste,
        "rastit": [],
        "leimaustapa": leimaustavat
        }

    if reset == str(1):
        with urllib.request.urlopen("http://hazor.eu.pythonanywhere.com/2021/data.json") as response:
            data = simplejson.load(response)
    else:
        with io.open("data.json", "r", encoding="UTF-8") as file:
            data = simplejson.load(file)
    if tila == "delete":
        poista_joukkue(data, sarja, nimi, False)
    if tila == "insert":
        lisaa_joukkue(data, sarja, joukkue, False)
    if tila == "update":
        paivita(data, tunniste, joukkue, sarja)

    koodit = rastien_koodit(data)
    joukkueet1 = joukkueet_eka(data)
    joukkueet2 = joukkueet_toka(data)
    joukkueet3 = joukkueet_kolmas(data)

    JSONtiedosto = simplejson.dumps(data)
    with io.open("data.json", "w", encoding="UTF-8") as file:
        file.write(JSONtiedosto)

    tulos = joukkueet1 + "\n\n" + koodit + "\n\n" + joukkueet2 + "\n\n" + joukkueet3
    resp = make_response(tulos)
    resp.mimetype = "text/plain"
    return resp

@app.route("/data.json")
def json():
    with io.open("data.json", "r", encoding="UTF-8") as file:
        data = simplejson.load(file)
    response = app.response_class(
        response=simplejson.dumps(data),
        status=200,
        mimetype='application/json'
    )
    return response