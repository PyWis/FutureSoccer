import random
import string

MALE_NAMES = [
    'Alessandro', 'Andrea', 'Antonio', 'Carlo', 'Cristian',
    'Davide', 'Diego', 'Edoardo', 'Emanuele', 'Enrico',
    'Fabio', 'Federico', 'Filippo', 'Francesco', 'Gabriele',
    'Giacomo', 'Gianluca', 'Giorgio', 'Giovanni', 'Giuseppe',
    'Leonardo', 'Lorenzo', 'Luca', 'Luigi', 'Manuel',
    'Marco', 'Massimo', 'Matteo', 'Mattia', 'Maurizio',
    'Michele', 'Nicola', 'Nicolò', 'Paolo', 'Pietro',
    'Raffaele', 'Riccardo', 'Roberto', 'Salvatore', 'Sergio',
    'Simone', 'Stefano', 'Thomas', 'Tommaso', 'Umberto',
    'Valentino', 'Valerio', 'Vincenzo', 'Enzo', 'Daniele',
]

FEMALE_NAMES = [
    'Alessandra', 'Alessia', 'Alice', 'Angela', 'Anna',
    'Aurora', 'Beatrice', 'Bianca', 'Camilla', 'Carlotta',
    'Caterina', 'Chiara', 'Claudia', 'Cristina', 'Diana',
    'Elena', 'Eleonora', 'Elisa', 'Emanuela', 'Federica',
    'Francesca', 'Gabriella', 'Giorgia', 'Giulia', 'Gloria',
    'Ilaria', 'Irene', 'Jessica', 'Laura', 'Lucia',
    'Luisa', 'Maria', 'Martina', 'Matilde', 'Monica',
    'Noemi', 'Paola', 'Patrizia', 'Rachele', 'Roberta',
    'Sara', 'Serena', 'Silvia', 'Sofia', 'Stefania',
    'Teresa', 'Valentina', 'Valeria', 'Veronica', 'Vittoria',
]

SURNAMES = [
    'Rossi', 'Russo', 'Ferrari', 'Esposito', 'Bianchi',
    'Romano', 'Colombo', 'Ricci', 'Marino', 'Greco',
    'Bruno', 'Gallo', 'Conti', 'Mancini', 'Costa',
    'Giordano', 'Rizzo', 'Lombardi', 'Moretti', 'Barbieri',
    'Fontana', 'Santoro', 'Mariani', 'Rinaldi', 'Caruso',
    'Ferrara', 'Galli', 'Martini', 'Leone', 'Longo',
    'Gentile', 'Martinelli', 'Vitale', 'Lombardo', 'Serra',
    'Coppola', 'Marchetti', 'Parisi', 'Villa', 'Conte',
    'Ferretti', 'Palumbo', 'Ferrario', 'Sartori', 'Cattaneo',
    'Bernardi', 'Pellegrini', 'Fabbri', 'Valentini', 'Piras',
    'Monti', 'Donati', 'Mele', 'Giuliani', 'Negri',
    'Neri', 'Sala', 'Poli', 'Riva', 'Ferri',
    'Piana', 'Basile', 'Grasso', 'Fiore', 'Silvestri',
    'Damiani', 'Rossetti', 'Bruni', 'Sanna', 'Benedetti',
    'Caputo', 'Battaglia', 'Testa', 'Guerra', 'Ferreri',
    'Amato', 'Pacini', 'Orlando', 'Morelli', 'Messina',
    'Marini', 'Farina', 'Ferraro', 'Ruggiero', 'Bianco',
    'Castelli', 'Pinto', 'Napoli', 'Renzi', 'Quaglia',
    'Fiorillo', 'Mazza', 'De Luca', 'De Santis', "D'Angelo",
    'De Rosa', 'De Marco', 'Giannini', 'Riccardi', 'Vitali',
]

SPONSOR_NAMES = [
    'NeoTech Industries', 'CyberCorp Italia', 'Quantum Motors',
    'Stellar Energy', 'BioForce Labs', 'Nexus Global',
    'HelioStar Systems', 'AeroVision SPA', 'TurboGen Corp',
    'MegaNet Italia', 'CryoTech Systems', 'PlasmaForce Ltd',
    'VoltexPrime', 'OmegaDrive SPA', 'HyperLink Corp',
    'FusionWave Italia', 'NovaCraft Systems', 'ZenithPower SPA',
    'AquaNex Corp', 'GalaxySports Brand', 'IronPulse Corp',
    'ThunderVolt SPA', 'LuminaX Group', 'CoreFlex Systems',
    'AstraForce Ltd', 'ByteStorm Italia', 'PhotonDrive Corp',
]

PLAYER_TYPES = ['uomo', 'donna', 'cyber']


def generate_cyber_code():
    chars = string.ascii_uppercase + string.digits
    return ''.join(random.choices(chars, k=6))


def random_player_name(ptype):
    if ptype == 'cyber':
        return generate_cyber_code()
    elif ptype == 'uomo':
        return f"{random.choice(MALE_NAMES)} {random.choice(SURNAMES)}"
    else:
        return f"{random.choice(FEMALE_NAMES)} {random.choice(SURNAMES)}"


def random_sponsor_name(exclude=None):
    available = [s for s in SPONSOR_NAMES if s != exclude]
    return random.choice(available)
