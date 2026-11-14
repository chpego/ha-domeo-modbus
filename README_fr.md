# S&P DOMEO EVO pour Home Assistant

<img src="https://raw.githubusercontent.com/chpego/ha-domeo-modbus/main/custom_components/domeo_modbus/brand/icon.png" alt="" width="96" align="right">

- Lire et piloter une VMC double flux **S&P DOMEO EVO** (225, 315, 450 ; FL, RD, DHU, Sérénité) depuis Home Assistant, par son port Modbus RTU.
- Entièrement local : par une passerelle RS485 vers Modbus TCP ou un adaptateur USB RS485. Ni cloud, ni compte.
- Configuration depuis l'interface, en français ou en anglais.

[![Release][release-shield]][release]
[![Downloads][downloads-shield]][release]
[![License][license-shield]](LICENSE)
[![Tests][tests-shield]][tests]
[![Hassfest][hassfest-shield]][hassfest]
[![Repository validation][validation-shield]][validation]

[English version](README.md)

> [!NOTE]
> Cette intégration est en **bêta**. Les registres suivent la table officielle S&P, et les premières vraies VMC sont en test sur le [forum HACF](https://forum.hacf.fr/t/vmc-s-p-domeo-evo-225-fl-via-modbus-tcp-rtu/69801). Voir [Limites connues](#limites-connues).

## Sommaire

- [Fonctionnalités](#fonctionnalités)
- [VMC prises en charge](#vmc-prises-en-charge)
- [Prérequis](#prérequis)
- [Installation](#installation)
- [Configuration](#configuration)
- [Mise à jour des données](#mise-à-jour-des-données)
- [Entités](#entités)
- [Ce que l'intégration écrit](#ce-que-lintégration-écrit)
- [Exemple d'automatisation](#exemple-dautomatisation)
- [Limites connues](#limites-connues)
- [Dépannage](#dépannage)
- [Contribuer](#contribuer)
- [Projets liés](#projets-liés)
- [Avertissement et licence](#avertissement-et-licence)

## Fonctionnalités

- **En local.** Rien ne sort de votre réseau.
- **Configuration depuis l'interface.** Le type de liaison (passerelle réseau ou port série), le modèle et la variante.
- **Débits dans les limites de la VMC.** Les débits bas, haut et freecooling sont bornés selon votre modèle.
- **Sondes AIRSENS détectées automatiquement.** Un capteur par sonde d'humidité, de CO₂ ou de COV branchée.
- **Signale le cavalier JP1.** Une entité de diagnostic et une réparation vous préviennent quand la VMC ignore les commandes Modbus.
- **Sans risque pour la liaison.** Elle n'écrit jamais l'adresse, la vitesse ni la parité de la VMC.
- **Diagnostic.** Téléchargement en un clic, avec la carte brute des registres et l'adresse de la passerelle masquée.
- **Traduite.** Français et anglais.

## VMC prises en charge

| VMC | État | Preuve |
| --- | --- | --- |
| **DOMEO EVO 225 RD** | Lectures et commandes confirmées | Deux vraies 225 RD ([#6](https://github.com/chpego/ha-domeo-modbus/issues/6), [#12](https://github.com/chpego/ha-domeo-modbus/issues/12)) : lectures, mode vacances, démarrage du boost. Le reset filtre est en cours de confirmation. |
| DOMEO EVO 225 FL | Devrait fonctionner | Même VMC avec une commande filaire, pas encore testée |
| DOMEO EVO 315, 450 | Devrait fonctionner | Même table de registres ; plages de débit par modèle selon la table S&P |
| Variantes DHU, Sérénité | Devrait fonctionner | Régulation hygro et sondes AIRSENS selon la table S&P, testées sur un simulateur |
| Domeo 210 FL et DHU (ancienne gamme) | En test | Construite sur les deux tables S&P de 2017 (FL, et DHU pour la France) et un YAML Domeo 210 utilisé depuis 2021 ; pas encore testée par un propriétaire ([#15](https://github.com/chpego/ha-domeo-modbus/issues/15)). Choisissez **Domeo 210** dans la liste des modèles, puis FL ou DHU. |

**Domeo 210, encore à confirmer sur une vraie VMC :** l'ordre des registres input 22 et 23 (température de rejet, puis d'air neuf), et l'activation du mode vacances et du by-pass automatique avec 1. Les deux tables de 2017 le disent ; une table plus ancienne, de 2014, dit l'inverse. La DHU a aussi ses réglages de régulation hygro ; elle ne transmet aucune mesure d'humidité par Modbus. La 210 ne signale pas le cavalier JP1 : une commande refusée est le seul signe que JP1 est ouvert. Dans la version Europe (trois vitesses et veille), il n'y a pas de bouton boost, et l'interrupteur vacances devient un interrupteur de veille.

**Non prises en charge :** le reste de l'ancienne gamme Domeo (ancienne Domeo DHU ou Hygro, Flexeo, Ideo, et l'Atacama vendue par Leroy Merlin). Elle utilise d'autres tables de registres, où les mêmes adresses correspondent à d'autres réglages : l'intégration refuse donc ces VMC si on les ajoute comme DOMEO EVO ([#7](https://github.com/chpego/ha-domeo-modbus/issues/7)). Ici, « DHU » désigne la DOMEO EVO DHU. L'Atacama aurait la même carte que la Domeo 210 (sujet HACF 3947) : l'ajouter comme Domeo 210 pourrait fonctionner, mais personne ne l'a encore essayé.

**Pourquoi `domeo_modbus` ?** Le nom technique (domaine `domeo_modbus`, dépôt `ha-domeo-modbus`) n'est pas lié à la gamme EVO : l'ancienne gamme Domeo entre donc dans cette même intégration, avec sa propre table de registres ([#15](https://github.com/chpego/ha-domeo-modbus/issues/15), testeurs bienvenus). L'intégration s'affiche toujours sous le nom **S&P DOMEO EVO**.

Vous avez l'une de ces VMC ? Un retour avec votre fichier de diagnostic est le bienvenu : [ouvrez une issue](https://github.com/chpego/ha-domeo-modbus/issues).

## Prérequis

- Home Assistant **2026.10.2** ou plus récent.
- Cavalier **JP1** fermé sur la carte de la VMC. JP1 ouvert, la VMC répond aux lectures mais refuse toutes les commandes. Une fois JP1 fermé, la VMC obéit aux commandes Modbus. D'après S&P, une commande filaire ne fonctionne alors plus ; une télécommande radio (RD) continue de fonctionner, comme l'a montré la VMC d'un testeur ([#12](https://github.com/chpego/ha-domeo-modbus/issues/12)). Coupez l'alimentation avant d'ouvrir la VMC.
- Une liaison vers le bornier RS485 de la VMC (A, B, GND) :
  - une **passerelle** (Waveshare RS485 TO ETH, Elfin EW11…) en mode **Modbus TCP vers RTU**, ou
  - un **adaptateur USB RS485** sur la machine Home Assistant.
- Réglages de ligne : **19200 bauds, 8 bits de données, parité paire, 1 bit de stop**. Ce sont les réglages d'usine. 9600 bauds ou 2 bits de stop, parfois conseillés ailleurs, ne fonctionnent pas.

## Installation

### Marketplace

[![Ouvrir ce dépôt dans le Marketplace de votre Home Assistant.](https://my.home-assistant.io/badges/marketplace_repository.svg)](https://my.home-assistant.io/redirect/marketplace_repository/?owner=chpego&repository=ha-domeo-modbus)

Ou à la main : **Paramètres → Marketplace → ⋮ → Dépôts personnalisés**, ajoutez `https://github.com/chpego/ha-domeo-modbus` avec le type **Intégration**, puis téléchargez **S&P DOMEO EVO**.

### Versions bêta

Les bêtas sont publiées en pré-versions GitHub. Pour les recevoir, ouvrez ce dépôt dans le Marketplace et activez son option **Pré-version**.

### Depuis la 0.2.0-beta.1

Depuis la 0.2.0-beta.2, l'intégration s'appelle `domeo_modbus` au lieu de `domeo_evo`, et le dépôt `ha-domeo-modbus` au lieu de `ha-domeo-evo` ([#10](https://github.com/chpego/ha-domeo-modbus/issues/10)). Home Assistant ne peut pas reprendre l'ancienne entrée, donc :

1. Dans **Paramètres → Appareils et services**, supprimez l'entrée **S&P DOMEO EVO**.
2. Dans le **Marketplace**, supprimez l'intégration, puis téléchargez-la à nouveau depuis ce dépôt.
3. Redémarrez Home Assistant et ajoutez à nouveau la VMC ([Configuration](#configuration)).

Les identifiants d'entité viennent du nom de la VMC : ils restent les mêmes, et vos automatisations continuent de fonctionner.

### À la main

Copiez `custom_components/domeo_modbus` dans votre dossier `config/custom_components/` et redémarrez Home Assistant.

## Configuration

[![Commencer la configuration de S&P DOMEO EVO dans votre Home Assistant.](https://my.home-assistant.io/badges/config_flow_start.svg)](https://my.home-assistant.io/redirect/config_flow_start/?domain=domeo_modbus)

Ou **Paramètres → Appareils et services → Ajouter une intégration → S&P DOMEO EVO**, puis :

1. Choisissez **Réseau** (passerelle) ou **Port série** (adaptateur USB).
2. Indiquez l'adresse et le port de la passerelle (souvent 502), ou le port série.
3. Laissez l'ID à **1**, sauf si vous l'avez changé.
4. Choisissez le **modèle** inscrit sur la plaque (225, 315 ou 450) et la **variante**. La VMC ne les indique pas, et ils fixent les plages de débit et les réglages hygro.

Pour changer plus tard l'adresse de la passerelle ou la liaison, utilisez **Reconfigurer** sur l'intégration. La VMC n'a pas de numéro de série : l'ajouter une seconde fois créerait un deuxième appareil.

## Mise à jour des données

- **Lectures** (débit, températures, mode, alarmes, interrupteurs, sondes) : toutes les 30 secondes.
- **Réglages** (débits, seuils, intervalles) : toutes les 5 minutes, et juste après une modification.
- **Pannes partielles :** chaque partie de la VMC est lue séparément. Si l'une ne répond pas, seules ses entités deviennent indisponibles.
- **Passerelle muette :** après trois lectures sans réponse d'affilée, la liaison est rouverte. Certaines passerelles gardent la connexion ouverte alors que la VMC derrière elles ne répond plus.

Home Assistant partage une seule connexion par passerelle et envoie une requête à la fois. Si un autre programme (configuration YAML `modbus:`, Node-RED…) interroge la même passerelle, coupez-le ou activez le mode **multi-hôte** de la passerelle.

## Entités

| Type | Entités |
| --- | --- |
| Capteurs | Débit, mode de fonctionnement, les cinq températures d'air, batterie de préchauffage, télécommande, entrée 0-10 V ; humidité intégrée (DHU, Sérénité) ; un capteur par sonde AIRSENS (humidité, CO₂ ou COV) |
| Capteurs binaires | Remplacement du filtre, dégivrage, défauts moteurs, défauts des sondes de température, contact CLP, **Pilotage Modbus (JP1)** |
| Interrupteurs | Mode vacances, by-pass manuel, by-pass automatique, dégivrage autorisé |
| Boutons | Démarrer le boost, réinitialiser l'alarme filtre |
| Listes | Mode automatique (proportionnel ou agile), type de contact CLP |
| Nombres | Débits bas, haut et freecooling (bornés selon le modèle), seuils de by-pass, durée du by-pass manuel, intervalle du filtre, correction et décalage du débit ; régulation hygro et qualité d'air (DHU, Sérénité) |

Certaines entités de diagnostic et de configuration sont désactivées par défaut. Activez-les depuis la page de l'appareil.

Un bouton affiche **Inconnu** tant qu'il n'a jamais été pressé. C'est le fonctionnement normal de Home Assistant, pas une erreur.

## Ce que l'intégration écrit

Rien, tant que vous n'utilisez pas une commande. Elle n'écrit jamais les registres 40001 à 40003 (adresse, vitesse et parité de la VMC) : une mauvaise valeur y coupe la liaison au prochain redémarrage. Elle ne propose pas la réinitialisation des ID AIRSENS (coil 9), qui oublie les sondes appairées. Elle ne lit que les adresses documentées dans la table S&P.

## Exemple d'automatisation

Lancer un boost quand la salle de bain devient humide. La VMC arrête le boost d'elle-même au bout de 30 minutes ; il ne peut pas être arrêté plus tôt par Modbus. Remplacez les identifiants d'entité par les vôtres (avec Home Assistant en français, le bouton s'appelle par exemple `button.domeo_evo_225_fl_demarrer_le_boost`).

```yaml
alias: "VMC : boost quand la salle de bain est humide"
triggers:
  - trigger: numeric_state
    entity_id: sensor.salle_de_bain_humidite
    above: 70
actions:
  - action: button.press
    target:
      entity_id: button.domeo_evo_225_fl_demarrer_le_boost
mode: single
```

> [!WARNING]
> Ne recopiez pas les anciens exemples YAML qui appellent `modbus.write_register` avec `address: 2` : ce registre est la **parité** de la VMC, et l'écrire coupe la liaison au prochain redémarrage.

## Limites connues

- **Mode vacances.** La table S&P indique pour le coil 4 « 0 = On », mais les retours de deux vraies VMC indiquent l'inverse : l'intégration le lit et l'écrit donc en « 1 = On » ([#6](https://github.com/chpego/ha-domeo-modbus/issues/6)). Si l'interrupteur affiche le contraire de ce que fait votre VMC, signalez-le dans une issue.
- **Pas d'arrêt du boost.** La table dit qu'écrire 0 arrête le boost, mais une vraie VMC l'ignore (en FC06 comme en FC16), et le support S&P a confirmé qu'un boost ne peut pas être arrêté par Modbus. Il s'arrête seul au bout de 30 minutes, l'intégration n'a donc pas de bouton d'arrêt.
- **Pas de boost en mode vacances.** Une vraie VMC ne lance pas de boost tant que le mode vacances est activé. Le bouton de boost affiche alors un message demandant de désactiver d'abord le mode vacances.
- **Reset du filtre.** En cours de confirmation sur de vraies VMC. L'intégration écrit le coil 8, comme l'indique la table.

## Dépannage

| Symptôme | Cause et solution |
| --- | --- |
| Une réparation indique *le cavalier JP1 est ouvert*, ou les commandes échouent avec *exception 0x01* | JP1 est ouvert. Coupez le courant, fermez JP1, rallumez. L'entité **Pilotage Modbus (JP1)** passe à « activé ». |
| La configuration indique *la VMC ne répond pas* | Mauvais réglages de ligne ou câblage. Vérifiez 19200 bauds, 8E1, A/B non inversés, et la passerelle en Modbus TCP vers RTU. |
| La VMC ne répond plus après une coupure de courant | Sa parité a peut-être été changée par une écriture YAML erronée dans le registre 40003 (adresse 2). Essayez la parité impaire sur la passerelle, puis réécrivez `2` dans ce registre. |
| Humidité bloquée à 54 % | Aucun capteur d'humidité n'est monté (VMC FL et RD). C'est ce que renvoie la VMC. |
| Température avant échangeur inconnue | Aucune sonde n'est montée à cet endroit ; la VMC la signale en défaut. |

### Logs de débogage

Sur la carte de l'intégration : **⋮ → Activer la journalisation de débogage**, reproduisez le problème, puis **⋮ → Désactiver la journalisation de débogage** pour télécharger le journal.

### Diagnostic

Sur la carte de l'intégration : **⋮ → Télécharger les diagnostics**. Joignez le fichier à une [issue](https://github.com/chpego/ha-domeo-modbus/issues). L'adresse de la passerelle y est masquée.

## Contribuer

Les signalements de bugs et les retours de tests sur de vraies VMC sont les bienvenus, en français ou en anglais. Le détail technique (tests, bibliothèque embarquée, releases) est dans la [version anglaise](README.md#contributing).

## Projets liés

- [xtozez/homeassistant-domeo-evo-225fl-modbus](https://github.com/xtozez/homeassistant-domeo-evo-225fl-modbus) : la configuration YAML à l'origine du projet, avec la table officielle des registres S&P (PDF).
- [Fil du forum HACF](https://forum.hacf.fr/t/vmc-s-p-domeo-evo-225-fl-via-modbus-tcp-rtu/69801) : câblage, passerelles et retours sur de vraies VMC.
- [timlaing/modbus_local_gateway](https://github.com/timlaing/modbus_local_gateway) : une intégration Modbus générique qui propose un fichier pour la DOMEO EVO. Utilisez l'une ou l'autre sur la même passerelle, ou activez le multi-hôte.

## Avertissement et licence

Projet indépendant, sans lien avec S&P (Soler & Palau) ni Unelvent. À utiliser sous votre responsabilité : les commandes modifient le fonctionnement de votre ventilation.

[MIT](LICENSE)

[release-shield]: https://img.shields.io/github/v/release/chpego/ha-domeo-modbus.svg?include_prereleases
[release]: https://github.com/chpego/ha-domeo-modbus/releases
[downloads-shield]: https://img.shields.io/github/downloads/chpego/ha-domeo-modbus/total.svg
[license-shield]: https://img.shields.io/github/license/chpego/ha-domeo-modbus.svg
[tests-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/tests.yml/badge.svg
[tests]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/tests.yml
[hassfest-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hassfest.yml/badge.svg
[hassfest]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hassfest.yml
[validation-shield]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hacs.yml/badge.svg
[validation]: https://github.com/chpego/ha-domeo-modbus/actions/workflows/hacs.yml
