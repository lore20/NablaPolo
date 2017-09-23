# ∇Polo: Un servizio di carpooling per gli utenti del Polo Scientifico di
  Sesto Fiorentino 

∇Polo è un bot telegram attualmente in parte basato sulle api di Google Apps
Engine (principalmente per quanto riguarda il data storage). Allo stato
attuale riesce a funzionare sul devserver GAE.

Nasce da un fork di [PickMeUp](https://github.com/kercos/PickMeUp), sviluppato
da un gruppo di volontari per il Trentino
([pickmeup.trentino.it](http://pickmeup.trentino.it))

## Utilizzo
============
Un file `key.py` deve essere creato nella root basandosi sul formato di
`key.py.example`.

È inoltre necessario creare un virtualenv python per ospitare le librerie
richieste. Segue un elenco di esempio di comandi da eseguire per soddisfare le
dipendenze richieste (funzionamento non garantito):

	   cd $NablaPoloRoot
	   pip install virtualenv
	   virtualenv -p /usr/bib/python2 ./
	   source ./bin/activate
	   pip install -t lib -r requirements.txt --upgrade
	   dev_appserver.py --host $server_ip --port $server_port ./

