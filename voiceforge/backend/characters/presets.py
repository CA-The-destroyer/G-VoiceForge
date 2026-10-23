GROUPS={
 'Humans':['Farmer','Blacksmith','Soldier','Knight','Nobleman','Noblewoman','Merchant','Innkeeper','Priest','Witch','Bandit','Beggar','Elderly villager','Child'],
 'Humanoids':['Goblin','Hobgoblin','Orc','Gnoll','Bugbear','Ogre','Troll'],
 'Undead':['Skeleton','Zombie','Ghoul','Wight','Vampire','Lich','Revenant','Ghost'],
 'Mythological':['Succubus','Siren','Hag','Banshee','Harpy','Demon']}

def presets():
    result=[]
    for group,names in GROUPS.items():
        for name in names:
            effect={'Goblin':'goblin','Vampire':'vampire','Skeleton':'skeleton','Ghost':'ghost','Ogre':'ogre'}.get(name,'clean')
            texture='rough' if group=='Humanoids' else 'airy' if name in ('Ghost','Siren') else 'clear'
            result.append({'name':name,'group':group,'texture':texture,'effect':effect,
                          'note':'Descriptive direction; use a suitable reference performance. Nonverbal sounds require separate recordings.'})
    return result
