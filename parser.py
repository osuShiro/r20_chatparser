import re, json, os, datetime, codecs
from copy import deepcopy
from lxml import html, etree
from tkinter import filedialog
from time import strptime

# TO DO: DEFENSE ROLLS

def get_webpage_from_file():
    filename = filedialog.askopenfilename(title='HTML file to parse')
    return html.fromstring(open(filename, 'r', encoding='utf-8').read())

def remove_whitespace(text_list):
    return ''.join(map(lambda t: re.sub(r'\s+',' ',t),text_list)).strip()

# extract roll details from the inlinerollresult span title
def get_roll_details(sheet_roll):
    roll = sheet_roll.find_class('inlinerollresult')[0]
    return remove_whitespace(html.fromstring(roll.get('title')).itertext())

def parse_log():
    chatlog=[]
    print('Importing file...')
    messages_html = get_webpage_from_file().find_class('message')
    print('Parsing chatlog...')
    cur_time = None
    cur_owner = None
    for msg in messages_html:
        parsed_message = {}
        temp = deepcopy(msg)
        msg_classes = list(temp.classes)
        # add message owner
        owner = temp.find_class('by')
        if owner:
            # last character will always be ":" which we don't want
            cur_owner = owner[0].text_content()[:-1]
        parsed_message['owner'] = cur_owner
        # add message timestamp
        timestamp = temp.find_class('tstamp')
        if timestamp:
            cur_time = timestamp[0].text_content() # '%B %d, %Y %I:%M%p'
        parsed_message['timestamp'] = cur_time
        if 'general' in msg_classes:
            sheet_rolls = temp.find_class('sheet-rolltemplate-pf_generic')
            attacks = temp.find_class('sheet-rolltemplate-pf_attack')
            spells = temp.find_class('sheet-rolltemplate-pf_spell')
            abilities = temp.find_class('sheet-rolltemplate-pf_ability')
            if sheet_rolls:
                parsed_message['type'] = 'skill roll'
                for sheet_roll in sheet_rolls:
                    # text comes with a ton of whitespace that we need to remove
                    parsed_message['text'] = remove_whitespace(sheet_roll.find_class('sheet-left')[0].itertext())
                    parsed_message['roll_detail'] = get_roll_details(sheet_roll)
                    # first cell is the left one and only has "check"
                    # we want the second one for the roll result
                    parsed_message['result'] = sheet_roll.find_class('sheet-roll-cell')[1].text_content().strip()
                    # some skill checks have notes
                    description = sheet_roll.find_class('sheet-roll-description')
                    if description:
                        parsed_message['notes'] = description[0].text_content().strip()
                    else:
                        parsed_message['notes'] = ''
            elif attacks:
                attack_rolls = []
                parsed_message['type'] = 'attack'
                for attack in attacks:
                    # text comes with a ton of whitespace that we need to remove
                    try:
                        parsed_message['text'] = remove_whitespace(attack.find_class('sheet-left')[0].itertext())
                    except:
                        parsed_message['text'] = ''
                    rows = attack.find_class('sheet-roll-row')
                    # last two children are damage type and notes, which we have to treat differently
                    for row in rows[:-2]:
                        attack_roll = {}
                        children = row.getchildren()
                        attack_roll['name'] = children[0].text_content().strip()
                        # extract roll details from the inlinerollresult span title
                        try:
                            attack_roll['roll_detail'] = parsed_message['roll_detail'] = get_roll_details(sheet_roll)
                            # result
                            attack_roll['result'] = children[1].text_content()
                        except:
                            attack_roll['roll_detail'] = ''
                            attack_roll['result'] = ''
                        attack_rolls.append(attack_roll)
                    parsed_message['attacks'] = attack_rolls
                    try:
                        parsed_message['notes'] = rows[-1].text_content()
                    except:
                        parsed_message['notes'] = ''
            elif spells:
                parsed_message['type'] = 'spell'
                for spell in spells:
                    try:
                        parsed_message['text'] = remove_whitespace(spell.find_class('sheet-left')[0].itertext()).strip()
                    except:
                        continue
            elif abilities:
                parsed_message['type'] = 'ability'
                for ability in abilities:
                    parsed_message['text'] = remove_whitespace(ability.find_class('sheet-left')[0].itertext()).strip()
                    parsed_message['roll_detail'] = get_roll_details(sheet_roll)
                    try:
                        parsed_message['result'] = ability.find_class('sheet-roll-cell')[1].text_content().strip()
                    except:
                        parsed_message['result'] = ''
            else:
            # the actual text will always be 4th child and onwards
                parsed_message['type'] = 'message'
                parsed_message['text'] = ''
                # print(list(temp.itertext()))
                #for child in temp.getchildren():
                    #if child.tag == 'em':
                        #parsed_message['text'] = parsed_message['text'] + '*' + child.text + '*'
                    #elif child.tag == 'strong':
                        #parsed_message['text'] = parsed_message['text'] + '**' + child.text + '**'
                parsed_message['text'] = parsed_message['text'] + list(temp.itertext())[-1].strip()
        elif 'emote' in msg_classes:
            parsed_message['type'] = 'action'
            parsed_message['text'] = temp.text_content().strip()
        elif 'desc' in msg_classes:
            parsed_message['type'] = 'description'
            parsed_message['text'] = temp.text_content().strip()
        elif 'rollresult' in msg_classes:
            parsed_message['type'] = 'roll'
            parsed_message['formula'] = temp.find_class('formula')[0].text_content().strip()
            roll_list = []
            rolls = temp.find_class('diceroll')
            for roll in rolls:
                roll_list.append(roll.find_class('didroll')[0].text_content())
            parsed_message['rolls'] = ','.join(roll_list)
            parsed_message['result'] = temp.find_class('rolled')[0].text_content().strip()
        else:
            continue
        chatlog.append(parsed_message)

    with open('output.txt','w', encoding='utf8') as output:
        json.dump(chatlog, output)

    return json.dumps(chatlog)

def split_sessions(chatlog_json):
    # filename = filedialog.askopenfilename(title='chatlog output to split')
    chatlog = json.loads(chatlog_json)
    if os.path.exists('./sessions'):
        print('Emptying folder...')
        for file in os.scandir('./sessions'):
            os.unlink(file.path)
    else:
        os.mkdir('./sessions')
    os.chdir('./sessions')
    cur_date = None
    output_file = None
    session_log = []
    print('Exporting chatlog...')
    for line in chatlog:
        try:
            timestamp = datetime.datetime.strptime(line['timestamp'], '%B %d, %Y %I:%M%p').replace(hour=0, minute=0)
        except:
            timestamp = cur_date
        if timestamp == cur_date:
            session_log.append(line)
        elif timestamp != cur_date:
            cur_date = timestamp
            filename = '-'.join([str(cur_date.year), str(cur_date.month).zfill(2), str(cur_date.day).zfill(2)])
            if output_file:
                output_file.write(json.dumps(session_log))
                output_file.close()
                session_log = []
                print('Writing ' + filename + '.txt...')
            output_file = open(filename+'.txt', 'w')
        else:
            print('Something went wrong with the timestamp.')
    output_file.write(json.dumps(session_log))
    output_file.close()


split_sessions(parse_log())
