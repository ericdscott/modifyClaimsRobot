#!/usr/bin/python
# -*- coding: utf-8 -*-
"""
TODO: flesh this out

"""
#
# Distributed under the terms of MIT License.
#
from __future__ import absolute_import, unicode_literals

__version__ = '$Id$'
#
import sys
reload(sys)
sys.setdefaultencoding('utf-8')
import re
import signal
import string
import time
import urlparse
import httplib
import requests
import pywikibot.data.sparql as sparql
import pywikibot
from pywikibot import pagegenerators as pg, textlib, WikidataBot
from pywikibot.data import sparql

willstop = False

def uniqueMember (lst):
    assert len(lst) == 1
    return lst[0]

            
def qNumberFor(s):
    m = re.match(".*(Q[0-9]+).*", str(s))
    if m:
        result = m.groups(1)
        if type(result) == type(()):
            x, = result
            return x
        else:
            assert type(result) == type("")
            return result

# strips ? from vars
removeQMark=lambda s: s.strip('?')

class ModifyClaimsRobot(WikidataBot):
    """A bot to query for erroneous Wikidata claims, and replace them with 
    correct ones."""

    def __init__(self, generator, bindings, commentForBindingFn,
                 itemVar=None,
                 sourcePredicate=None,
                 targetPredicate=None,
                 themeVar=None,
                 skipDeletionVar=None,
                 skipAdditionVar=None):
        """
        Constructor.

        Arguments:
        <generator> -- should be a sparql generator.
        <bindings> := [<binding>, ...]
        <commentForBindingFn> := fn(binding) -> <comment>
        """
        super(ModifyClaimsRobot, self).__init__()

        g = pg.PreloadingGenerator(generator)
        print ("g:%s" % g)
        self.generator=pg.PreloadingGenerator(generator)
        self.bindings=bindings # item-id -> bindings
        self.commentForBinding = commentForBindingFn 
        self.item=lambda binding: binding[removeQMark(itemVar)]
        self.sourcePredicate=sourcePredicate
        self.targetPredicate=targetPredicate
        self.theme=lambda binding: binding[removeQMark(themeVar)]
        def referenceIfDefined (var):
            def test_binding(binding):
                if not var:
                    return False
                x = binding.get(removeQMark(var), 'false')
                if not x:
                    return False
                # x is of type 'pywikibot.data.sparql.Literal'
                x = str(x)
                # pywikibot.output("x:%s/%s/%s" % (x , str(x) == 'true', type(x)))
                result = (x == 'true')
                if result:
                    pywikibot.output("Skipping %s/%s" % (var, binding))
                return result
            return test_binding
        self.skipDeletion=referenceIfDefined(skipDeletionVar)
        self.skipAddition=referenceIfDefined(skipAdditionVar)

    def treat(self, itemPage):
        """
        Side-effect: Removes assertions <item> <source predicate> <theme>, 
          unless skipDeletion(binding)
        Side-effect: Adds assertions <item> <target predicate> <theme>, 
          unless skipAddition(binding)
        Side-effect: Assertions of 'source' in the source predicate are 
          moved to the new assertion. unless there is no new source.
     
        Where 
        <item> is the Q associated with <item page>
        <source predicate> is the P-number of some ill-expressed assertion
        <target predicate> is the P-number of some better assertion
        <theme> is the Q-number of the inappropriate object of
          <source predicate> which should be moved to <target predicate>
        <binding> is a binding from the originating SPARQL expression
        """
        pywikibot.output("page:%s" % itemPage.getID()) # type(itemPage))

        contents = itemPage.get()
        # <contents> := {'claims' : {<P> : [<claim>, ...]...},...}

        # Assuming that each query acquires a single assertion per item...
        binding = uniqueMember(self.bindings[itemPage.getID()])
        summary = self.commentForBinding(binding)

        def matchesBinding(claim):
            # True if <claim> has the same target as the theme of <binding>
            b_target = qNumberFor (self.theme(binding)) 
            c_target = qNumberFor (str(claim.getTarget()))
            return (b_target == c_target)

        
        offendingClaims = [c 
                           for c in contents['claims'][self.sourcePredicate]
                           if matchesBinding(c)]

        # pywikibot.output("offending claims:%s " % offendingClaims)
                
        for c in offendingClaims:
            newClaim = (pywikibot.Claim(self.repo, self.targetPredicate)
                        if not self.skipAddition(binding)
                        else None)
            if newClaim:
                newClaim.setTarget(c.getTarget())
                if not pywikibot.config.simulate:
                    itemPage.addClaim(newClaim, summary=summary)

                else:
                    pywikibot.output ("SIMULATION: adding %s " % newClaim)
                    pywikibot.output ("SIMULATION: comment %s " % summary)

                for source in c.getSources():
                    for sourceProp, source_values  in source.items():
                        newSource = pywikibot.Claim(self.repo, 
                                                     sourceProp,
                                                     isReference = True)
                        newSource.setTarget(source_values[0].getTarget())
                        if not pywikibot.config.simulate:
                            newClaim.addSource(newSource)
                        else:
                            pywikibot.output ("SIMULATION: adding source %s" 
                                              % newSource)
            if not self.skipDeletion(binding):
                if not pywikibot.config.simulate:
                    itemPage.removeClaims([c], summary=summary)
                else:
                    pywikibot.output ("SIMULATION: deleting %s  " % c)
                    pywikibot.output ("SIMULATION: comment %s  " % summary)
                assert len(c.qualifiers) == 0
                #pywikibot.output("qualifiers:%s" % c.qualifiers)
            

def processQuery(sparqlQuery, 
                  itemVar = None,
                  ):
    """
    Returns (<item page generator>, <bindings>) for <sparqlQuery>
    """
    assert itemVar

    site = pywikibot.Site()
    repo =  site.data_repository()
    query = sparql.SparqlQuery(repo = repo)
    idFor = lambda item: item.getID()
    bindings = {}
    for binding in query.select(sparqlQuery, full_data=True) :
        item = binding[removeQMark(itemVar)]
        entry = bindings.get(item, [])
        bindings[idFor(item)] = entry + [binding]


    itemPageFor = lambda id: pywikibot.ItemPage(repo, id)
    pywikibot.output("keys:%s" % bindings.keys())
    itemsPages = (itemPageFor(id)
                   for id in bindings.keys()
                   if pywikibot.ItemPage.is_valid_id(id))
    for binding in bindings.values():
        print pywikibot.output(binding)
    #return (pg.WikidataPageFromItemGenerator(itemsPages, site), bindings)
    return (itemsPages, bindings)


def anachronisticScreenwriters(*args):
    """
    Moves 'screenwriter' assertions to 'based on a work by' assertions 
    in cases where the screenwriter died before the advent of cinema.
    """
    pywikibot.output("args in anachronisticScreenwriters:%s" % list(args))
    pywikibot.config.simulate = False #True
    # gen = pg.GeneratorFactory()

    anachronistic_screenwriters_query = """

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
Limit 100
"""

    editParameters = {
        "itemVar" : "?movie",
        "sourcePredicate" : "P58",
        "targetPredicate" : "P1877",
        "themeVar" : "?deadGuy",
        "skipDeletionVar" : None,
        "skipAdditionVar" : "?alreadyAdded"
        }

    def commentForBinding(binding):
        return ("%s was dead long before there were screenwriters. "
                % binding['deadGuyLabel']
                + "Should be 'after a work by'")


    itemPage_generator, bindings = processQuery(
        anachronistic_screenwriters_query, 
        itemVar=editParameters['itemVar'])
    
    
    bot = ModifyClaimsRobot(itemPage_generator, 
                            bindings, 
                            commentForBinding,
                            **editParameters)
    bot.run()
    #result = gen.handleArg("-sparql:%s" % query)
    #bot = ModifyClaimsRobot(gen.getCombinedGenerator())
    
    



if __name__ == "__main__":
    pywikibot.output("argv going in:%s" % sys.argv)
    anachronisticScreenwriters()
