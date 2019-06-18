import re, json, os, datetime, codecs
from copy import deepcopy
from lxml import html, etree
from tkinter import filedialog
from sys import exit
from time import strptime

# TO DO: DEFENSE ROLLS

# debugging function
def log_html(tag):
    print('Exporting tag as log.txt')
    with open('log.txt','wb') as logfile:
        logfile.write(html.tostring(tag, pretty_print=True))
    exit()

def get_webpage_from_file():
    filename = filedialog.askopenfilename(title='HTML file to parse')
    return html.fromstring(open(filename, 'r', encoding='utf-8').read())

# removes the masses of unnecessary whitespace around the HTML page
def remove_whitespace(text_list):
    return ''.join(map(lambda t: re.sub(r'\s+',' ',t),text_list)).strip()

# extract roll details from the inlinerollresult span title
def get_roll_details(sheet_roll):
    roll = sheet_roll.find_class('inlinerollresult')[0]
    return remove_whitespace(html.fromstring(roll.get('title')).itertext()).strip()

def get_text(message):
    return remove_whitespace(message.find_class('sheet-left')[0].itertext()).strip()

def parse_sheet_rolls(sheet_rolls, parsed_message):
    parsed_message['type'] = 'skill roll'
    for sheet_roll in sheet_rolls:
        parsed_message['text'] = get_text(sheet_roll)
        parsed_message['roll_detail'] = get_roll_details(sheet_roll)
        # for skill rolls, first cell is the left one and only has "check"
        # we want the second one for the roll result
        parsed_message['result'] = sheet_roll.find_class('sheet-roll-cell')[1].text_content().strip()
        # some skill checks have notes
        description = sheet_roll.find_class('sheet-roll-description')
        if description:
            parsed_message['notes'] = description[0].text_content().strip()
        else:
            parsed_message['notes'] = ''

def parse_sheet_attacks(attacks, parsed_message):
    attack_rolls = []
    parsed_message['type'] = 'attack'
    for attack in attacks:
        # text comes with a ton of whitespace that we need to remove
        try:
            parsed_message['text'] = get_text(attack)
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
                attack_roll['result'] = children[1].text_content().strip()
            except:
                attack_roll['roll_detail'] = ''
                attack_roll['result'] = ''
            attack_rolls.append(attack_roll)
        parsed_message['attacks'] = attack_rolls
        try:
            parsed_message['notes'] = rows[-1].text_content().strip()
        except:
            parsed_message['notes'] = ''

def parse_spells(spells, parsed_message):
    parsed_message['type'] = 'spell'
    for spell in spells:
        # TODO: remove this terrible hack of a job and handle the spell case properly
        try:
            parsed_message['text'] = get_text(spell)
        except:
            continue

def parse_abilities(abilities, parsed_message):
    parsed_message['type'] = 'ability'
    for ability in abilities:
        parsed_message['text'] = get_text(ability)
        try:
            parsed_message['result'] = ability.find_class('sheet-roll-cell')[1].text_content().strip()
        except:
            parsed_message['result'] = ''

def parse_log():
    chatlog=[]
    print('Importing file...')
    messages_html = get_webpage_from_file().find_class('message')
    print('Parsing chatlog...')
    cur_time = None
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
            defences = temp.find_class('sheet-rolltemplate-pf_defense')
            if sheet_rolls:
                parse_sheet_rolls(sheet_rolls, parsed_message)
            elif attacks:
                parse_sheet_attacks(attacks, parsed_message)
            elif spells:
                parse_spells(spells, parsed_message)
            elif abilities:
                parse_abilities(abilities, parsed_message)
            elif defences:
                # TODO: proper handling of defence rolls
                parsed_message['type'] = 'defence'
            else:
                parsed_message['type'] = 'message'
                # checking the div for the spacer child to check if it's the first message from a new user
                if temp.find_class('spacer'):
                    # first four children are spacer, avatar, timestamp and owner
                    # which we don't want in the message
                    parsed_message['text'] = ''.join(list(temp.itertext())[3:]).strip()
                # if it's the same user but a new message, they aren't there, and the tag as no children just text
                else:
                    parsed_message['text'] = temp.text_content().strip()
        else:
            parsed_message['owner'] = ''
            if 'emote' in msg_classes:
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

def export_dialogue_lines(chatlog):
    lines = []
    for line_dic in chatlog:
        if line_dic['type'] == 'message':
            lines.append(line_dic['owner'] + ': ' + line_dic['text'])
        if line_dic['type'] in ('description','action'):
            lines.append(line_dic['text'])
    return lines

def export_dialogue(chatlog_json):
    print('Exporting dialogue...')
    lines = export_dialogue_lines(json.loads(chatlog_json))
    with open('dialogue.txt','w', encoding='utf-8') as file_output:
        for line in lines:
            file_output.write(line)
            file_output.write('\n')

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
    session_log = []
    print('Exporting chatlog...')
    for line in chatlog:
        try:
            timestamp = datetime.datetime.strptime(line['timestamp'], '%B %d, %Y %I:%M%p').replace(hour=0, minute=0)
            if not cur_date:
                cur_date = timestamp
        except:
            # sometimes the timestamp will be missing hours and minutes
            # but then we don't care since we're only looking at day and month
            # so the day of the session doesn't change
            timestamp = cur_date
        if timestamp == cur_date:
            session_log.append(line)
        elif timestamp != cur_date:
            # export chatlog to a text file
            filename = '-'.join([str(cur_date.year), str(cur_date.month).zfill(2), str(cur_date.day).zfill(2)])
            print('Writing ' + filename + '.txt...')
            output_file = open(filename + '.txt', 'w')
            output_file.write(json.dumps(session_log))
            output_file.close()
            # reset log then add the first line
            cur_date = timestamp
            session_log = []
            session_log.append(line)
        else:
            print('Something went wrong with the timestamp.')
    # export last chatlog that wasn't done in the loop
    filename = '-'.join([str(timestamp.year), str(timestamp.month).zfill(2), str(timestamp.day).zfill(2)])
    print('Writing ' + filename + '.txt...')
    output_file = open(filename + '.txt', 'w')
    output_file.write(json.dumps(session_log))
    output_file.close()


chatlog = parse_log()
split_sessions(chatlog)
export_dialogue(chatlog)