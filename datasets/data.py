import math

# NODES (Coordinates)

nodes = {
    'A': (1, 1),
    'B': (3, 1),
    'C': (5, 1),
    'D': (7, 1),

    'E': (1, 3),
    'F': (3, 3),
    'G': (5, 3),
    'H': (7, 3),

    'I': (1, 5),
    'J': (3, 5),
    'K': (5, 5),
    'L': (7, 5),

    'M': (1, 7),
    'N': (3, 7),
    'O': (5, 7),
    'P': (7, 7),

    'Q': (2, 9),
    'R': (4, 9),
    'S': (6, 9),
    'T': (8, 9)
}

# NODE TYPES

node_types = {
    # Hospitals (inside city)
    'F': 'hospital',
    'K': 'hospital',

    # Safe Zones (outskirts / top)
    'Q': 'safe_zone',
    'T': 'safe_zone',

    # Residential clusters (disaster-prone areas)
    'A': 'residential',
    'B': 'residential',
    'C': 'residential',
    'D': 'residential',
    'E': 'residential',
    'G': 'residential',
    'H': 'residential',
    'I': 'residential',
    'J': 'residential',
    'L': 'residential',

    # Remaining → junctions (implicitly)
}

edges = {
    'A': [
        ('B', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('E', {'distance': 2, 'road_type': 'street', 'traffic': 'high', 'condition': 'damaged'})
    ],
    'B': [
        ('A', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('C', {'distance': 2, 'road_type': 'highway', 'traffic': 'low', 'condition': 'good'}),
        ('F', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'C': [
        ('B', {'distance': 2, 'road_type': 'highway', 'traffic': 'low', 'condition': 'good'}),
        ('D', {'distance': 2, 'road_type': 'highway', 'traffic': 'low', 'condition': 'good'}),
        ('G', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'D': [
        ('C', {'distance': 2, 'road_type': 'highway', 'traffic': 'low', 'condition': 'good'}),
        ('H', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],

    'E': [
        ('A', {'distance': 2, 'road_type': 'street', 'traffic': 'high', 'condition': 'damaged'}),
        ('F', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('I', {'distance': 2, 'road_type': 'street', 'traffic': 'high', 'condition': 'damaged'})
    ],
    'F': [
        ('B', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('E', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('G', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('J', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'G': [
        ('C', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('F', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('H', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('K', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'H': [
        ('D', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('G', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('L', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],

    'I': [
        ('E', {'distance': 2, 'road_type': 'street', 'traffic': 'high', 'condition': 'damaged'}),
        ('J', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('M', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'J': [
        ('F', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('I', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('K', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('N', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'K': [
        ('G', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('J', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('L', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('O', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],
    'L': [
        ('H', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('K', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('P', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'})
    ],

    'M': [
        ('I', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('N', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('Q', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'N': [
        ('J', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('M', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('O', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('R', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'O': [
        ('K', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('N', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('P', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('S', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'P': [
        ('L', {'distance': 2, 'road_type': 'street', 'traffic': 'medium', 'condition': 'good'}),
        ('O', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('T', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],

    'Q': [
        ('M', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('R', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'R': [
        ('N', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('Q', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('S', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'S': [
        ('O', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('R', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('T', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ],
    'T': [
        ('P', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'}),
        ('S', {'distance': 2, 'road_type': 'street', 'traffic': 'low', 'condition': 'good'})
    ]
}

BASE_SPEED = {
    'highway': 60,   # km/h
    'street': 40,
    'narrow': 20
}

TRAFFIC_FACTOR = {
    'low': 1.0,
    'medium': 0.7,
    'high': 0.4
}

CONDITION_FACTOR = {
    'good': 1.0,
    'damaged': 0.6,
    'blocked': 0.1
}

# weight calculation 
def compute_edge_weight(edge):
    distance = edge['distance']

    base_speed = BASE_SPEED[edge['road_type']]
    traffic = TRAFFIC_FACTOR[edge['traffic']]
    condition = CONDITION_FACTOR[edge['condition']]

    effective_speed = base_speed * traffic * condition

    # avoid division by zero
    if effective_speed == 0:
        return float('inf')

    travel_time = distance / effective_speed

    return round(travel_time, 5)

# RESCUERS

rescuers = [
    {
        'id': 'R1',
        'location': 'F',
        'team_size': 5,
        'vehicle_type': 'ambulance',
        'speed_factor': 1.0,
        'status': 'free'
    },
    {
        'id': 'R2',
        'location': 'K',
        'team_size': 4,
        'vehicle_type': 'ambulance',
        'speed_factor': 1.0,
        'status': 'free'
    },
    {
        'id': 'R3',
        'location': 'J',
        'team_size': 3,
        'vehicle_type': 'helicopter',
        'speed_factor': 1.5,
        'status': 'free'
    },
    {
        'id': 'R4',
        'location': 'N',
        'team_size': 6,
        'vehicle_type': 'boat',
        'speed_factor': 0.8,
        'status': 'free'
    },
    {
        'id': 'R5',
        'location': 'B',
        'team_size': 4,
        'vehicle_type': 'ambulance',
        'speed_factor': 1.0,
        'status': 'free'
    },
    {
        'id': 'R6',
        'location': 'H',
        'team_size': 5,
        'vehicle_type': 'ambulance',
        'speed_factor': 1.0,
        'status': 'free'
    },
    {
        'id': 'R7',
        'location': 'O',
        'team_size': 3,
        'vehicle_type': 'helicopter',
        'speed_factor': 1.5,
        'status': 'free'
    },
    {
        'id': 'R8',
        'location': 'R',
        'team_size': 6,
        'vehicle_type': 'boat',
        'speed_factor': 0.8,
        'status': 'free'
    },
    {
    'id': 'R9',
    'location': 'C',
    'team_size': 4,
    'vehicle_type': 'ambulance',
    'speed_factor': 1.0,
    'status': 'free'
},
{
    'id': 'R10',
    'location': 'S',
    'team_size': 5,
    'vehicle_type': 'helicopter',
    'speed_factor': 1.5,
    'status': 'free'
}
]

def get_rescuers():
    return rescuers

# RESCUE REQUESTS

requests = [
    {'id': 'Q1', 'location': 'A', 'people': 25, 'severity': 'critical', 'request_time': 0},
    {'id': 'Q2', 'location': 'B', 'people': 15, 'severity': 'high', 'request_time': 1},
    {'id': 'Q3', 'location': 'C', 'people': 30, 'severity': 'critical', 'request_time': 2},
    {'id': 'Q4', 'location': 'D', 'people': 10, 'severity': 'medium', 'request_time': 3},

    {'id': 'Q5', 'location': 'E', 'people': 20, 'severity': 'high', 'request_time': 1},
    {'id': 'Q6', 'location': 'G', 'people': 35, 'severity': 'critical', 'request_time': 0},
    {'id': 'Q7', 'location': 'H', 'people': 12, 'severity': 'medium', 'request_time': 4},

    {'id': 'Q8', 'location': 'I', 'people': 18, 'severity': 'high', 'request_time': 2},
    {'id': 'Q9', 'location': 'J', 'people': 40, 'severity': 'critical', 'request_time': 1},

    {'id': 'Q10', 'location': 'L', 'people': 8, 'severity': 'medium', 'request_time': 5}
]

def get_requests():
    return requests

SEVERITY_SCORE = {
    'critical': 3,
    'high': 2,
    'medium': 1
}

def compute_priority(request, distance, current_time):
    severity_score = SEVERITY_SCORE[request['severity']]
    people_score = math.log(request['people'] + 1)

    waiting_time = current_time - request['request_time']

    distance_factor = 1 / (distance + 1)

    priority = (
        severity_score +
        people_score +
        waiting_time +
        distance_factor
    )

    return round(priority, 5)

def get_graph():
    return nodes, edges

def get_distance(node1, node2):
    x1, y1 = nodes[node1]
    x2, y2 = nodes[node2]

    return ((x1 - x2)**2 + (y1 - y2)**2) ** 0.5

def get_node_type(node):
    return node_types.get(node, 'junction')

def get_edge_weight(edge):
    return compute_edge_weight(edge)

def get_priority(request, rescuer_location, current_time):
    distance = get_distance(rescuer_location, request['location'])
    return compute_priority(request, distance, current_time)