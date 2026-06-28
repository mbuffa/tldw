# Too Long; Didn't Watch

A Youtube video summarizer that leverages your Ollama server to save you 30 minutes of anxiety, slashed ad breaks or infinite ego to extract the essential information.

And it supports Caveman.

## Disclaimer
This app was written using agentic coding. I did make all the technical choices in here, including using LangChain and Astral's modern Python tooling, but I needed an app quickly. So there might be ugly spots here and there yet.

Also, support your favorite creators by watching their videos, of course. I just needed a summary for all the stocks and trading related videos that last 35 minutes for a couple of useful statements :)

## Install
This is a self-hosted application, you'll need:
* (optional) `asdf` and its python plugin
* `make`

```sh
make sync
make run
make test
```

There's also a simple PoC shell script you can use to tinker with the prompt or to have a good laugh:
```sh
./tldw hHGPsHTHaLA
```

```
**Uhhh... Écoute bien, petit oiseau.**

De grands têtes, ils jouent avec nombres et lignes droits. Ils voient dans 
Bitcoin une loi de la nature… grand prix pour toi après beaucoup-beaucoup 
temps. Mais ces calculs sont fausses magies, ils disent trop de choses 
sans preuve réelle.

Le coin est toujours sauvage, mon ami. Les modèles ne diront pas où le 
bison va tomber ; seulement que les grands risquent d'être très... 
*riche*. Ugh.
```
