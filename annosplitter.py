import os
import subprocess
import xml.etree.ElementTree as ET

# constants
INPUT_PATH = "./input"
OUTPUT_PATH = "./output"
FFMPEG_PATH = "./ffmpeg/bin/ffmpeg.exe"
FFMPEG_GLOBAL_OPTIONS = "-y -an" # force overwrite, remove audio
FFMPEG_CODEC = "libx264"
FFMPEG_CONTAINER = "mp4"
DETACHED_PROCESS = 0x00000008

# defaults
TARGET_TIER = "RH-IDgloss"
PADDING = 0

# For media file locations, BSL Corpus EAFs have hard references to a Mac-style volume mount
# Need to convert those to a Windows drive mapping for the time being
# Comment these lines out if you're running on a Mac and use Finder to connect to the Corpus volume
MEDIA_PATH_REPLACE = "file:///Volumes/ritd-ag-project-rd00iz-kcorm83"
MEDIA_PATH_WITH = "Z:/"

# global vars
time_table = {}

# get user input
temp = input("Enter tier to be searched (default = RH-IDgloss): ")
if temp != "": TARGET_TIER = temp

ANNOTATION_MATCH = input("Substring that annotations must contain (default = all annotations): ")

temp = input("Milliseconds of padding (default = 0): ")
if temp != "": PADDING = int(temp)

# walk through all EAF files in input folder
for path, dirs, files in os.walk(INPUT_PATH):  
    for file in files:
        path_to_file = path + "/" + file
        file_name, file_ext = os.path.splitext(file)
        if file_ext == ".eaf":
            # parse the XML of this EAF
            print("Parsing " + file_name + " ...")
            doc_root = ET.parse(path_to_file).getroot()
            # load all time slots into a table ( id : milliseconds ) for ease of reference later
            time_table.clear()
            for doc_timeslot in doc_root.find("TIME_ORDER").iter("TIME_SLOT"):
                time_table[doc_timeslot.get("TIME_SLOT_ID")] = doc_timeslot.get("TIME_VALUE")
            # BSL Corpus media filenames are not well conventionalised ... For now, use the media file with the shortest filename
            doc_header = doc_root.find("HEADER")
            media_path = None
            for descriptor in doc_header.iter("MEDIA_DESCRIPTOR"):
                if not media_path or len(descriptor.get("MEDIA_URL")) < len(media_path):
                    media_path = descriptor.get("MEDIA_URL")
                    media_offset = descriptor.get("TIME_ORIGIN")
            media_path = media_path.replace(MEDIA_PATH_REPLACE, MEDIA_PATH_WITH)
            # search for target annotations on target tier
            for doc_tier in doc_root.iter("TIER"):
                if doc_tier.get("TIER_ID") == TARGET_TIER:
                    for doc_annotation in doc_tier.iter("ANNOTATION"):
                        # "Alignable" annotations (parent tiers) refer directly to time slots
                        sub_annotation = doc_annotation.find("ALIGNABLE_ANNOTATION")
                        if sub_annotation and sub_annotation.find("ANNOTATION_VALUE").text and sub_annotation.find("ANNOTATION_VALUE").text.find(ANNOTATION_MATCH) > -1:
                            # Shorten BSL Corpus filename convention to region, participant and task (e.g. BL09C)
                            short_file_name = file_name[:4] + file_name.replace("_LH","")[-1:]
                            # get annotation ID
                            sub_id = sub_annotation.get("ANNOTATION_ID")
                            # look up start and end times from table
                            sub_start = float(time_table[sub_annotation.get("TIME_SLOT_REF1")])
                            sub_end = float(time_table[sub_annotation.get("TIME_SLOT_REF2")])
                            # if this media file has an offset, apply it
                            if media_offset:
                                sub_start += float(media_offset)
                                sub_end += float(media_offset)
                            # convert to seconds and then a string
                            sub_start = str((sub_start - PADDING) / 1000)
                            sub_end = str((sub_end + PADDING) / 1000)
                            # create ffmpeg command line
                            cmdline = FFMPEG_PATH + " " + FFMPEG_GLOBAL_OPTIONS
                            # set start end time in seconds
                            cmdline += " -ss " + sub_start + " -to " + sub_end
                            # define input file
                            cmdline += " -i \"" + media_path + "\""
                            # define output codec and filename
                            cmdline += " -c:v " + FFMPEG_CODEC + " \"" + OUTPUT_PATH + "\\" + short_file_name + "_" + time_table[sub_annotation.get("TIME_SLOT_REF1")] + "_" + time_table[sub_annotation.get("TIME_SLOT_REF2")] + "." + FFMPEG_CONTAINER + "\""
                            # run ffmpeg in a separate windowless process
                            print("Processing annotation " + sub_id + " (" + sub_start + " to " + sub_end +")")
                            subprocess.run(cmdline, creationflags=DETACHED_PROCESS)
                        # But "reference" annotations reference an ALIGNABLE in the parent tier, sigh
                        # TODO

input("Finished! Press Enter to close: ")
