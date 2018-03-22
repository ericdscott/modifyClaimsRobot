# modifyClaimsRobot

This is a module intended to be executed within the pywikibot ecosystem. It is posted here as part of the process of securing permission to run a bot against the Wikidata servers.

It defines a class ModifyClaimsRobot, extending WididataBot. It is informed by a SPARQL query which identifies erroneous assertions, exemplified by the case where say Victor Hugo is asserted as the screenwriter of a movie. 

There is an additional specification that identifies variables bound by the query to various roles within the bot run. For example, this query, posed to the Wididata SPARQL endpoint...

```
    PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
    PREFIX http: <http://www.w3.org/2011/http#>
    prefix wdt: <http://www.wikidata.org/prop/direct/>
    prefix wd: <http://www.wikidata.org/entity/>

Select Distinct ?movie ?title ?deadGuy ?deadGuyLabel ?dateOfDeath 
                ?alreadyAdded
Where
{
    Bind (wdt:P570 as ?dateOfDeathP)
    ?movie wdt:P58 ?deadGuy;
        rdfs:label ?title. Filter (Lang(?title) = "en")
    ?deadGuy rdfs:label ?deadGuyLabel. Filter (Lang(?deadGuyLabel) = "en")
    ?deadGuy ?dateOfDeathP ?dateOfDeath.
    Filter (?dateOfDeath < "1910-01-01T00:00:00Z"^^xsd:dateTime)
    Optional
    {
      ?movie wdt:P1877 ?deadGuy;
      Bind (true as ?alreadyAdded)
    }
}
```
Is paired with ....
```
    editParameters = {
        "itemVar" : "?movie",
        "sourcePredicate" : "P58",
        "targetPredicate" : "P1877",
        "themeVar" : "?deadGuy",
        "skipDeletionVar" : None,
        "skipAdditionVar" : "?alreadyAdded"
}
```

To indicate that WD items associated with ?movie whose screenwriter is ?deadGuy, known to have died before 1910, should have assertions with P59 (screenwriter) replaced with assertions of P1877 (from a work by), and that new P1877 claims should be skipped if such an assertion has already been added.

Provinencne information attached to the original P59 assertion will be asserted for the new P1877 claim.



