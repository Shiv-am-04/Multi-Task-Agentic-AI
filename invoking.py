from main_workflow import graph

def get_mail_output_from_graph(query,attachment_file=''):
    events = graph.stream({'question':[('user',f'''{query}, attachment : {attachment_file}''')]},stream_mode='values')

    try :
        for event in events:
            res = event.get('messages')
        return res
    except Exception:
        return False

def get_audio_output_from_graph(audio_file,query):
    events = graph.stream({'question':[('user',f'''{query} , file path : {audio_file}''')]},stream_mode='values')

    for event in events:
        res = event.get('messages')
    
    return res

def get_labels_output_from_graph(query,criteria='sender'):
    events = graph.stream({'question':[('user',f'''{query}, criteria :{criteria}''')]},stream_mode='values')

    for event in events:
        res = event.get('messages')
    
    return res

def get_web_output_from_graph(query):
    events = graph.stream({'question':query},stream_mode='values')

    for event in events:
        res = event.get('messages')
    
    return res

def get_output_from_graph(query):
    events = graph.stream({'question':[('user',query)]},stream_mode='values')

    for event in events:
        res = event.get('messages')
    
    return res