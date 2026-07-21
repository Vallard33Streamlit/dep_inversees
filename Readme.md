Ce dossier contient le code pour l'appli des "dépendances inversées"

Pour lancer l'appli en local, il faut :
•	(si ce dossier est déjà téléchargé cette étape n'est pas utile) cloner le repo : git clone https://github.com/Vallard33Streamlit/dep_inversees.git
•	installer python si ce n'est pas déjà fait
•	installer les modules utiles : pip install -r requirements.txt
•	lancer l'appli : streamlit run dev_inv.py

L'appli est aussi disponible sur ce lien : https://depinversees-4drjz8rewpxfffdn58kins.streamlit.app/

Les différents fichiers sont le code qui fait créer l'appli et fait tous les calculs : dep_inv. On trouve aussi Baci découpée en plusieurs morceaux pour qu'elle puisse être facilement téléversée sur github, le fichier d'AIPNET, la table de conversion de HS6 de 2022 à 2002 pour utiliser AIPNET. Il y a ensuite les codes des pays ainsi que leur noms et les associations codes HS labels.