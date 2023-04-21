import subprocess
from threading import Thread
from time import sleep, time
import os
from os import path
import a2s
import socket
import colorama
from colorama import Fore as Color

colorama.init()

srcds = None # SRCDS process
startupTime = 0 # Time when SRCDS was started
lastPing = time()

def warn(String):
    print(Color.RED + String + Color.RESET)


def notify(String):
    print(Color.GREEN + String + Color.RESET)


defaultConfigFile = """
#Delete this config and start the program again to regenerate this file with default values

#It's recommended to use srcds_console.exe (from Alien Swarm: Reactive Drop), because it doesn't create a second console window
executable=srcds_console.exe
args=-console -game garrysmod -console -port 27015 -norestart +maxplayers 32 +gamemode sandbox +map gm_construct

#Path to SteamCMD, set if you want to update the server automatically
steamCMDPath=

#If set, ping the server every second, and if doesn't respond for [timeBeforeForceRestart] seconds, restart it
#This should be set to your server's public IP address, with the port being the same as the one in the args
monitorIP=
monitorPort=27015
timeBeforeForceRestart=30

#Delay (in seconds) before starting watchdog, to allow the server to fully start up
startupDelay=30
"""

defaultConfig = {
    "executable": "srcds_console.exe",
    "args": "-console -game garrysmod -console -port 27015 -norestart +maxplayers 16 +gamemode sandbox +map gm_construct",
    "steamCMDPath": "",
    "monitorIP": "",
    "monitorPort": 27015,
    "timeBeforeForceRestart": 30,
    "startupDelay": 30
}


def loadConfig(f):
    config = {}

    with open(f) as file:
        for line in file:
            line = line.strip()

            if line.startswith("#") or len(line) == 0:
                continue

            parts = line.split("=", 1)

            if len(parts) == 2:
                key = parts[0].strip()
                value = parts[1].split("#")[0].strip()
                config[key] = value

    for key, value in defaultConfig.items():
        if key not in config:
            config[key] = value
            warn(f"Couldn't find {key} in config file, using default value")

    return config


if not path.exists("gmodwatchdog.cfg"):
    with open("gmodwatchdog.cfg", "w") as file:
        file.write(defaultConfigFile)
        warn("Config file not found, please edit the created gmodwatchdog.cfg file and restart the program")
        os.system("pause")
        exit(1)


config = loadConfig("gmodwatchdog.cfg")

executable = path.join(os.getcwd(), config["executable"])

if not path.exists(executable):
    warn(f"Executable not found, please make sure {config['executable']} exists")
    os.system("pause")
    exit(1)


def updateAddons():
    addonsDir = os.getcwd() + "/garrysmod/addons/"

    if not path.exists(addonsDir):
        warn("Addons directory does not exist")

        return

    dirs = [
        path.join(addonsDir, d)
        for d in os.listdir(addonsDir)
        if path.isdir(path.join(addonsDir, d))
    ]

    for d in dirs:
        if not path.exists(path.join(d, ".git")):
            continue

        addonName = d.replace(addonsDir, "")

        try:
            subprocess.run(["git", "pull"], cwd=d, check=True)
            notify(f"Successfully updated {addonName}")
        except subprocess.CalledProcessError as e:
            if e.returncode == 1:
                warn(f"Failed to update {addonName}: git error")
        except Exception as e:
            warn(f"Failed to update {addonName}: {e}")


def runSRCDS():
    global srcds
    global startupTime
    global lastPing
    global config

    config = loadConfig("gmodwatchdog.cfg")

    try:
        srcds = subprocess.Popen(f"{executable} {config['args']}")
        startupTime = time()
        lastPing = startupTime + int(config["startupDelay"])
        srcds.wait()
        srcds = None
    except Exception as e:
        warn(f"An error occurred while running SRCDS: {e}")

        return


def startServer():
    if srcds is None:
        updateAddons()
        Thread(target=runSRCDS).start()


def stopServer():
    global srcds

    if srcds is not None:
        srcds.terminate()
        srcds = None


def serverResponding():
    try:
        a2s.info((config["monitorIP"], int(config["monitorPort"])), timeout=1)

        return True
    except socket.timeout as e:
        return False
    except Exception as e:
        warn(f"An error occurred while querying server: {e}")

    return False


def watchdog():
    global lastPing

    while True:
        if startupTime == 0:
            continue

        runtime = time() - startupTime

        if srcds is not None and runtime > int(config["startupDelay"]) and config["monitorIP"] != "":
            if serverResponding():
                lastPing = time()
            else:
                print(Color.RED + "Server is not responding (last ping: " + str(int(time() - lastPing)) + " seconds ago)" + Color.RESET, end="\r")

            if time() - lastPing > int(config["timeBeforeForceRestart"]):
                warn("Server process is frozen, restarting in 5 seconds...")
                stopServer()
                sleep(5)
                startServer()
        elif srcds is None and runtime > 5:
            warn("Server process has stopped, restarting in 5 seconds...")
            sleep(5)
            startServer()

        sleep(1)


startServer()
Thread(target=watchdog).start()
os.system("title Server Manager")