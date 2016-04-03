# -*- coding: utf-8 -*-
# we don't import YAML handler for this 
# as no standard PYTHON handler library
import os.path
import datetime
from urlparse import urlparse

class SFYAMLHandler:
   
   sectioncount = 0
   identifiercount = 0
   
   YAMLSECTION = "---"
   YAMLNAMESPACE = 'name'
   YAMLDETAILS = 'details'

   header = {}

   HEADDETAILS = 'id_details'
   HEADNAMESPACE = 'id_namespace'
   HEADCOUNT = 'identifier_count'

   FILERECORDLEN = 6

   #structures for holding formst information
   filedetails = {}
   iddetails = {}

   #all files in report
   files = []

   fileheaders = ['filename', 'filesize', 'modified', 'errors', 'md5', 'sha1', 'sha256', 'sha512', 'crc']
   iddata = ['ns', 'id', 'format', 'version', 'mime', 'basis', 'warning']
   containers = {'zip': 'x-fmt/263', 'gz': 'x-fmt/266', 'tar': 'x-fmt/265', 'warc': 'fmt/289'}

   PROCESSING_ERROR = -1
   filecount = 0
   
   sfdata = {}
   DICTHEADER = 'header'
   DICTFILES = 'files'
   DICTID = 'identification'

   TYPECONT = 'Container'
   TYPEFILE = 'File'
   
   #additional fields given to SF output
   FIELDURI = 'uri'
   FIELDURISCHEME = 'uri scheme'
   FIELDDIRNAME = 'directory'
   FIELDYEAR = 'year'

   def stripkey(self, line):
      line = line.strip()
      line = line.replace('- ', '')
      return line

   def stripvalue(self, line):
      line = line.strip()
      line = line.lstrip("'").rstrip("'")
      return line

   def handleentry(self, line):
      line = line.split(':', 1)
      line[0] = self.stripkey(line[0])
      line[1] = self.stripvalue(line[1])
      return line

   def headersection(self, line):
      if line != self.YAMLSECTION:
         line = self.handleentry(line)
         if line[0] == self.YAMLNAMESPACE:
            self.identifiercount+=1
            ns = self.HEADNAMESPACE + str(self.identifiercount)
            self.header[ns] = line[1]
         elif line[0] == self.YAMLDETAILS:
            details = self.HEADDETAILS + str(self.identifiercount)
            self.header[details] = line[1]   
            self.header[self.HEADCOUNT] = self.identifiercount
         elif line[0] != 'identifiers':
            self.header[line[0]] = line[1]

   def filesection(self, sfrecord):
      iddict = {}    # { nsname : {id : x, mime : x } }  
      filedict = {}
      
      ns = ''
      iddata = {}
      
      for s in sfrecord:
         s = self.handleentry(s)
         if s[0] in self.fileheaders:
            filedict[s[0]] = s[1]  
            
            if s[0] == 'filename':
               fname = filedict['filename']
               fname = self.addFileURI(fname)
               for f in self.files:
                  needle_name = f['filename']
                  needle_type = f['type']
                  haystack = fname
                  if needle_name in haystack:
                     if needle_type == self.TYPECONT:
                        fname = self.addContainerURI(f, filedict, fname)                      
               filedict[self.FIELDURI] = fname
               filedict[self.FIELDURISCHEME] = self.geturischeme(fname)

         if s[0] in self.iddata:
            #add data to dict on NS trigger, create new dict
            if s[0] == 'ns':
               if len(iddata) > 0:
                  iddict[ns] = iddata
                  iddata = {}
               ns = s[1]               
            else:
               if s[0] == 'id':
                  self.getContainers(s[1], filedict)
               iddata[s[0]] = s[1]
      
      #on loop completion add final id record
      iddict[ns] = iddata
      
      #add complete id data to filedata, return
      filedict[self.DICTID] = iddict
      return filedict

   def readSFYAML(self, sfname):
      processing = False
      filedata = []
      with open(sfname, 'rb') as sfile:
         for line in sfile: 
            line = line.strip()
            if line == self.YAMLSECTION:
               self.sectioncount += 1
               # new section so handle appropriately 
               processing = False
            if self.sectioncount == 1:
               self.headersection(line)
            elif self.sectioncount > 1:
               if processing == False and len(filedata) > 0:
                  self.files.append(self.filesection(filedata))
                  filedata = []
               else:
                  processing = True
                  if line != self.YAMLSECTION: 
                     filedata.append(line)
      
      #Add final section of data to list
      if len(filedata) > 0:         
         self.files.append(self.filesection(filedata))
      
      #Attempt at useful return value - number of files processed vs. processing error
      if len(self.files) == self.sectioncount - 1:
         self.filecount = len(self.files)
      else:
         self.filecount = self.PROCESSING_ERROR
      
      #concatenate header and file details (not needed, but maybe convenient)
      self.sfdata[self.DICTHEADER] = self.header
      self.sfdata[self.DICTFILES] = self.files      
      return self.filecount

   def getDirName(self, filepath):
      return os.path.dirname(filepath)   

   def getFileName(self, filepath):
      return os.path.basename(filepath)
   
   def adddirname(self, sfdata):
      for row in sfdata[self.DICTFILES]:
         fname = row['filename']
         row[self.FIELDDIRNAME] = self.getDirName(fname) 
      return sfdata

   def addfilename(self, sfdata):
      for row in sfdata[self.DICTFILES]:
         fname = row['filename']
         row['name'] = self.getFileName(fname)
      return sfdata

   def addYear(self, sfdata):
      for row in sfdata[self.DICTFILES]:
         year = row['modified']
         row[self.FIELDYEAR] = self.getYear(year)
      return sfdata

   def getYear(self, datestring):
      #sf example: 2016-04-02T20:45:12+13:00
      datestring = datestring.replace('Z', '') #TODO: Handle 'Z' (Nato: Zulu) time (ZIPs only?)
      dt = datetime.datetime.strptime(datestring.split('+', 1)[0], '%Y-%m-%dT%H:%M:%S')
      return int(dt.year)

   def getContainers(self, id, filedict):
      #only set as File if and only if it isn't a Container
      #container overrides all...
      if id in self.containers.values():
         filedict['type'] = self.TYPECONT
         #get container type: http://stackoverflow.com/a/13149770
         filedict['containertype'] = self.containers.keys()[self.containers.values().index(id)]
      else:
         if 'type' in filedict:
            if filedict['type'] != self.TYPECONT:
               filedict['type'] = self.TYPEFILE
         else: 
            filedict['type'] = self.TYPEFILE 

   def addFileURI(self, fname):
      fname = "file:" + fname
      return fname

   def addContainerURI(self, container, containedfile, fname):
      fname = container['containertype'] + ":" + fname 
      fname = fname.replace(container['filename'], container['filename'] + "!")
      return fname

   def geturischeme(self, fname):
      return urlparse(fname).scheme

