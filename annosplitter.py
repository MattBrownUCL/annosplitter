import sys, os, subprocess
import xml.etree.ElementTree as ET

# constants
INPUT_PATH = "./input"
OUTPUT_PATH = "./output"
FFMPEG_PATH = "./ffmpeg/bin/ffmpeg.exe"
FFMPEG_GLOBAL_OPTIONS = "-y -an"
FFMPEG_CODEC_OPTIONS = "-c:v libx264 -vf scale=960:540"
FFMPEG_CONTAINER = "mp4"
DETACHED_PROCESS = 0x00000008

# defaults
padding = 0
target_tier = "RH-IDgloss"
annotation_match = ""

# For media file locations, BSL Corpus EAFs have hard references to a Mac-style volume mount
# Need to convert those to a Windows drive mapping for the time being
# Replace these values with None if you're running on a Corpus Mac, and use Finder to connect to the Corpus volume
MEDIA_PATH_REPLACE = "file:///Volumes/ritd-ag-project-rd00iz-kcorm83"
MEDIA_PATH_WITH = "Z:"

# Option to use the original HD capture files instead of the compressed ones specified in EAFs
# Replace the first with False to deactivate
MEDIA_QUALITY = True
MEDIA_QUALITY_REPLACE = "Compressed Files"
MEDIA_QUALITY_REPLACE_2 = "Compressed"
MEDIA_QUALITY_REPLACE_3 = ".compressed"
MEDIA_QUALITY_REPLACE_4 = "-comp"
MEDIA_QUALITY_WITH = "Original Capture"

# global vars
time_table = {}

# check output folder exists
if not os.path.exists(OUTPUT_PATH):
    print("Could not find \'" + OUTPUT_PATH + "\' folder, creating one.")
    os.makedirs(OUTPUT_PATH)

# check input folder exists
if not os.path.exists(INPUT_PATH):
    print("Could not find \'" + INPUT_PATH + "\' folder, creating one.")
    print("Copy the EAF files/folders you wish to process into the '" + INPUT_PATH + "' folder.")
    os.makedirs(INPUT_PATH)
    # stop - nothing to process
    sys.exit()

# get command line arguments
if len(sys.argv) >= 2: padding = int(sys.argv[1])
if len(sys.argv) >= 3: target_tier = sys.argv[2]
if len(sys.argv) >= 4: annotation_match = sys.argv[3]

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
            for doc_timeslot in doc_root.find("TIME_ORDER").findall("TIME_SLOT"):
                time_table[doc_timeslot.get("TIME_SLOT_ID")] = doc_timeslot.get("TIME_VALUE")
            # BSL Corpus media filenames are not very well conventionalised ... For now, use the media file with the shortest filename
            doc_header = doc_root.find("HEADER")
            media_path = None
            for descriptor in doc_header.findall("MEDIA_DESCRIPTOR"):
                if not media_path or len(descriptor.get("MEDIA_URL")) < len(media_path):
                    media_path = descriptor.get("MEDIA_URL")
                    media_offset = descriptor.get("TIME_ORIGIN")
            if MEDIA_PATH_REPLACE: media_path = media_path.replace(MEDIA_PATH_REPLACE, MEDIA_PATH_WITH)
            if MEDIA_QUALITY:
                    media_path = media_path.replace(MEDIA_QUALITY_REPLACE, MEDIA_QUALITY_WITH)
                    media_path = media_path.replace(MEDIA_QUALITY_REPLACE_2, MEDIA_QUALITY_WITH)
                    media_path = media_path.replace(MEDIA_QUALITY_REPLACE_3, "")
                    media_path = media_path.replace(MEDIA_QUALITY_REPLACE_4, "")
            # search for target annotations on target tier
            for doc_tier in doc_root.findall("TIER"):
                if doc_tier.get("TIER_ID") == target_tier:
                    for doc_annotation in doc_tier.findall("ANNOTATION"):
                        # "Alignable" annotations (parent tiers) refer directly to time slots
                        sub_annotation = doc_annotation.find("ALIGNABLE_ANNOTATION")
#                        if sub_annotation and sub_annotation.find("ANNOTATION_VALUE").text and sub_annotation.find("ANNOTATION_VALUE").text.find(annotation_match) > -1:
                        if (sub_annotation and sub_annotation.find("ANNOTATION_VALUE").text == annotation_match) or (annotation_match == ""):
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
                            # add padding, convert to seconds, convert to string
                            sub_start = str((sub_start - padding) / 1000)
                            sub_end = str((sub_end + padding) / 1000)
                            # create ffmpeg command line
                            cmdline = FFMPEG_PATH + " " + FFMPEG_GLOBAL_OPTIONS
                            # set start & end time in seconds
                            cmdline += " -ss " + sub_start + " -to " + sub_end
                            # define input file
                            cmdline += " -i \"" + media_path + "\""
                            # define output codec and filename
                            cmdline += " " + FFMPEG_CODEC_OPTIONS + " \"" + OUTPUT_PATH + "/" + short_file_name + "_" + time_table[sub_annotation.get("TIME_SLOT_REF1")] + "_" + time_table[sub_annotation.get("TIME_SLOT_REF2")] + "." + FFMPEG_CONTAINER + "\""
                            # run ffmpeg in a separate windowless process
                            print("Processing annotation " + sub_id + " ...")
                            if not os.path.exists(media_path): print("Error, media file not found: " + media_path)
                            #print(cmdline)
                            subprocess.run(cmdline, creationflags=DETACHED_PROCESS)
                        # But "reference" annotations reference an ALIGNABLE in the parent tier, sigh
                        # TODO

#input("Finished! Press Enter to close: ")
