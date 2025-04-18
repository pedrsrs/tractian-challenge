# Desafio de Scraping para Vaga da Tractian
~ Pedro Soares Pinto
## Justificando Escolhas de Bibliotecas

O site não possui detecção anti-bots. Mesmo sendo escrito com ASP.NET, os cookies de SessionId não são realmente verificados, logo, o uso de um WebDriver não é necessário.

Para esse projeto, optei por utilizar uma combinação de HTTPX (para envio de requests) e Selectolax (para parsing de html). 

- **HTTPX** possui suporte para requests assíncronas, diminuindo o tempo de execução com múltiplas requests simultâneas.


  
  https://oxylabs.io/blog/httpx-vs-requests-vs-aiohttp
  
- **Selectolax** é uma biblioteca de parsing de html escrita em C, com performance muito superior ao BeautifulSoup4 e a lxml (engine de parsing utilizada pelo Scrapy).



  https://medium.com/@yahyamrafe202/in-depth-comparison-of-web-scraping-parsers-lxml-beautifulsoup-and-selectolax-4f268ddea8df

Também implementei um aquivo models.py para validação de dados usando Pydantic. Um arquvio como esse não é completamente necessário para esse projeto mas seria muito útil ao longo prazo, com mais scrapers respeitando essa estrutura de output.

## Resultados

Usando requests assíncronas, obtive um tempo de execução médio de 30 segundos para 15 itens, ou 2 segundos por item.

![image](https://github.com/user-attachments/assets/a9ed5aaf-eb33-449c-9f99-a02cbb2a10e6)

#### Exemplo de output: 

![image](https://github.com/user-attachments/assets/ffe6745d-7ba9-4f41-9a33-2f5e71cc97bf)


#### OBS:
```python
        for category_id, category_item_count in reversed(list(category_data.items())):
```
Nesse trecho do código, inverti a lista de scraping das categorias de produtos pois as iniciais não possuiam arquivos .dwg, dessa forma facilitando a análise do output.
