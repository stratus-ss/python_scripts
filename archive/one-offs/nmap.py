#!/usr/bin/env python
# -*- coding: utf-8 -*-
import pygtk
import gtk
import os
import sys
import MySQLdb

database_connection = MySQLdb.connect('localhost', 'root', '', 'nmap');
cursor = database_connection.cursor()

class Application(gtk.Window):
    cells = {}
    columns = {}
    sort_order = gtk.SORT_ASCENDING
####################
    def __init__(self):
        gtk.Window.__init__( self )
        self.set_title("Netowrk Scanner")
        self.set_position(gtk.WIN_POS_CENTER)
        self.create_widgets()
        self.connect_signals()

        #self.window.show_all()
        self.show_all()
        gtk.main()
##################        
    def create_widgets(self):
        #Ask the user to search by operating system
        self.vbox = gtk.VBox(spacing=10)
        self.operating_system_label_hbox_1 = gtk.HBox(spacing=10)
        self.label = gtk.Label("Search by Operating System :")
        self.operating_system_label_hbox_1.pack_start(self.label)

        #Set a check box so the user can choose to display ports
        self.ports_hbox_8 = gtk.HBox(spacing=10)
        self.ports_check = gtk.CheckButton("Display Ports")
        self.ports_hbox_8.pack_start(self.ports_check)
        self.halign_ports = gtk.Alignment(0,1,1,0)
        self.halign_ports.add(self.ports_hbox_8)

        self.os_entry_hbox_2 = gtk.HBox(spacing=10)
        self.OS = gtk.Entry()
        self.os_entry_hbox_2.pack_start(self.OS)

        self.hostname_label_hbox_3 = gtk.HBox(spacing=10)
        self.label = gtk.Label("Search by Hostname:")
        self.hostname_label_hbox_3.pack_start(self.label)

        self.hostname_entry_hbox_4 = gtk.HBox(spacing=10)
        self.HOSTNAME = gtk.Entry()
        self.hostname_entry_hbox_4.pack_start(self.HOSTNAME)

        self.ip_label_hbox_5 = gtk.HBox(spacing=10)
        self.label = gtk.Label("Search by IP:")
        self.ip_label_hbox_5.pack_start(self.label)

        self.ip_entry_hbox_6 = gtk.HBox(spacing=10)
        self.IP = gtk.Entry()
        self.ip_entry_hbox_6.pack_start(self.IP)

        self.buttons_hbox_7 = gtk.HBox(spacing=10)
        self.button_ok = gtk.Button("Get Results!")
        self.buttons_hbox_7.pack_start(self.button_ok)
        self.button_exit = gtk.Button("Get me Outta Here!")
        self.buttons_hbox_7.pack_start(self.button_exit)

        #The order in which you pack_start a widget is the order in which it is displayed on the screen
        self.vbox.pack_start(self.operating_system_label_hbox_1)
        self.vbox.pack_start(self.os_entry_hbox_2)
        self.vbox.pack_start(self.hostname_label_hbox_3)
        self.vbox.pack_start(self.hostname_entry_hbox_4)
        self.vbox.pack_start(self.ip_label_hbox_5)
        self.vbox.pack_start(self.ip_entry_hbox_6)
        self.vbox.pack_start(self.halign_ports, False, False, 3)
        self.vbox.pack_start(self.buttons_hbox_7)

        self.add(self.vbox)
##########################
    def connect_signals(self):
        #Have the buttons start 'listening' for user interaction
        self.button_ok.connect("clicked", self.button_click)
        self.button_exit.connect("clicked", self.exit_program)
########################
    def button_click(self, clicked):
        #This function gets the values of the input boxes as well as the check box
        #And then passes them to the show_table function so it can get the correct results from the database
        global ports_check, os, ip, hostname
        os = self.OS.get_text()
        ip = self.IP.get_text()
        hostname = self.HOSTNAME.get_text()
        ports_check = self.ports_check.get_active()
        
        if os == "" and ip == "" and hostname == "":
            error_message = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, "You haven't entered anything to search for!")
            error_message.run()
            error_message.destroy()
        else:
            if hostname != "" and (os != "" or ip != ""):
                error_message = gtk.MessageDialog(self, gtk.DIALOG_DESTROY_WITH_PARENT, gtk.MESSAGE_ERROR, gtk.BUTTONS_CLOSE, "If you know the hostname why are you searching with other options? Please search by hostname only")
                error_message.run()
                error_message.destroy()
                self.OS.set_text("")
                self.IP.set_text("")
                self.HOSTNAME.set_text("")
            else:
                self.show_Table(os, ip, hostname)
##############        
    def show_Table(self, search_os, search_ip, search_hostname):
    ### Create the table
        # List of items to display which represent IP, OS, DNS, Port number and Port description
         # Columns
        if ports_check == True:
            cols = ['IP Address', 'Operating System', 'Hostname', 'Ports', 'Protocol Name']
        else:
            cols = ['IP Address', 'Operating System', 'Hostname']
        """    
        self.newColumn("IP Address", 0)
        self.newColumn("Operating System", 1)
        self.newColumn("Hostname",2)
        #I only want the ports columns to show if the user requests it because this calls different mysql querries
        if ports_check == True:
            self.newColumn("Ports", 3)
            self.newColumn("Protocol name", 4)
        """
        
        sequence = [str] * len(cols)
        self.treestore = gtk.TreeStore( * sequence)
        self.treestore.connect("rows-reordered", self.on_column_clicked)
        self.treeview = gtk.TreeView(self.treestore)
        self.treeview.cell = [None] * len(cols)
        self.treeview_column = [None] * len(cols)
        
        for column_number, col in enumerate(cols):
            self.treeview.cell[column_number] = gtk.CellRendererText()
            self.treeview_column[column_number] = gtk.TreeViewColumn(col, self.treeview.cell[column_number])
            self.treeview_column[column_number].add_attribute(self.treeview.cell[column_number], 'text', column_number)
            self.treeview_column[column_number].set_resizable(True)
            self.treeview_column[column_number].set_reorderable(True)
            self.treeview_column[column_number].set_sort_indicator(True)
            self.treeview_column[column_number].set_sort_column_id(column_number)
            self.treeview.append_column(self.treeview_column[column_number])
        
        self.scrollTree = gtk.ScrolledWindow()
        self.scrollTree.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)
        self.scrollTree.add(self.treeview)
        
        #If the user is running a search on the hostname run these querries
        if search_hostname != "":
            if ports_check == True:
                    cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name, Port_Description, Open_Port FROM Computer_Ports AS CP \
                        JOIN Computer_Info AS CI ON ( CP.Computer_ID = CI.Computer_ID ) \
                        JOIN Ports_Table AS PT ON ( CP.Port_ID = PT.Port_ID ) \
                        JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                        JOIN Port_Description AS PS ON ( PT.Open_Port = PS.Port_Number ) \
                        WHERE DNS_Name LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address ), Open_Port" % (search_hostname))
            #Otherwise just return the relevent data
            else:
                    cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name FROM Computer_Info AS CI  \
                        JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                        WHERE DNS_Name LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address )" % (search_hostname))
        
        
        #If the user has specified the IP and the OS to search, run this querry  
        if search_os != "" and search_ip !="":
        #Set up the querries. If the user has activted the checkbox, we need to include the ports in the querry
            if ports_check == True:
                 cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name, Port_Description, Open_Port FROM Computer_Ports AS CP \
                    JOIN Computer_Info AS CI ON ( CP.Computer_ID = CI.Computer_ID ) \
                    JOIN Ports_Table AS PT ON ( CP.Port_ID = PT.Port_ID ) \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    JOIN Port_Description AS PS ON ( PT.Open_Port = PS.Port_Number ) \
                    WHERE OS_Name LIKE '%%%s%%' and Computer_IP_Address LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address ), Open_Port" % (search_os, search_ip))
        #Otherwise just return the relevent data
            else:
                cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name FROM Computer_Info AS CI ON  \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    WHERE OS_Name LIKE '%%%s%%' and Computer_IP_Address LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address )" % (search_os, search_ip))
        #If the user has specified an OS but not an IP run this
        elif search_os != "" and search_ip == "":
            if ports_check == True:
                 cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name, Port_Description, Open_Port FROM Computer_Ports AS CP \
                    JOIN Computer_Info AS CI ON ( CP.Computer_ID = CI.Computer_ID ) \
                    JOIN Ports_Table AS PT ON ( CP.Port_ID = PT.Port_ID ) \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    JOIN Port_Description AS PS ON ( PT.Open_Port = PS.Port_Number ) \
                    WHERE OS_Name LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address ), Open_Port" % search_os)
            else:
                cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name FROM Computer_Info AS CI \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    WHERE OS_Name LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address )" % search_os)
        #If the user has specified an IP but not an OS run this
        elif search_os =="" and search_ip != "":
            if ports_check == True:
                cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name, Port_Description, Open_Port FROM Computer_Ports AS CP \
                    JOIN Computer_Info AS CI ON ( CP.Computer_ID = CI.Computer_ID ) \
                    JOIN Ports_Table AS PT ON ( CP.Port_ID = PT.Port_ID ) \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    JOIN Port_Description AS PS ON ( PT.Open_Port = PS.Port_Number ) \
                    WHERE Computer_IP_Address LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address ), Open_Port" % search_ip)
            else:
                 cursor.execute("SELECT DISTINCT Computer_IP_Address, OS_Name, DNS_Name FROM Computer_Info AS CI \
                    JOIN OS_Table AS OS ON ( CI.Computer_ID = OS.OS_ID ) \
                    WHERE Computer_IP_Address LIKE '%%%s%%' ORDER BY inet_aton( Computer_IP_Address )" % search_ip)

        #get the results and prepare to put them inside of lists
        fetch_results = cursor.fetchall()
        host_name_list = []
        operating_list = []
        ip_list = []
        ports = []
        #The element chosen to append to each list based on the order of retrieval in the mysql querry
        for individual_result in fetch_results:
            ip_list.append(individual_result[0])
            operating_list.append(individual_result[1])    
            host_name_list.append(individual_result[2])
            if ports_check == True:    
                ports.append(individual_result[3])
        #we are going to add blanks to the files in order to help readability
        #when putting this into the chart
        cleaned_host =[]
        cleaned_ip = []
        cleaned_os_list = []

        index_counter = 0
        #this loop will check to see if the entry already exists in the cleaned variables. If it does, it 'omitts' them by inserting a blank line
        while index_counter < len(host_name_list):
            if host_name_list[index_counter] in cleaned_host:
              #print "found a duplicate in HOST....OMITTING"
              cleaned_host.append("")
            else:
                #print "adding ", host_name_list[index_counter]  
                cleaned_host.append(host_name_list[index_counter])

            if operating_list[index_counter] in cleaned_os_list and ip_list[index_counter] in cleaned_ip:
                #print "found a duplicate in OPERATING....OMITTING"
                cleaned_os_list.append("")
            else:
                #print "adding ", operating_list[index_counter]     
                cleaned_os_list.append(operating_list[index_counter])

            if ip_list[index_counter] in cleaned_ip:
                #print "Found a duplicate in IP.... OMITTING "
                cleaned_ip.append("")
            else:
                #print "adding ", ip_list[index_counter]     
                cleaned_ip.append(ip_list[index_counter])
            index_counter +=1  

        #this section appends to the list store depending on whether the user wants to see the ports or not
        counter = 0
        for single_result in fetch_results:
            if ports_check == True:
                self.treestore.append( None,
            [ cleaned_ip[counter], cleaned_os_list[counter], cleaned_host[counter], single_result[4], single_result[3] ]
            )

            else:

                self.treestore.append(None,
            [ single_result[0], single_result[1], single_result[2] ]
            )
            counter +=1
        
        
        self.frm_table = gtk.Window()
        self.frm_table.set_default_size(600, 800)
        self.frm_table.set_title("Network scan results")
        #Change the background to white instead of grey
        self.frm_table.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#fff'))
        self.frm_table.add(self.scrollTree)
        self.frm_table.show_all()
###################### 
    def on_column_clicked(self, col1, col2, col3, col4 ):
        #This function allows the columns to be resorted upon click

        if self.sort_order == gtk.SORT_ASCENDING:
            self.sort_order = gtk.SORT_DESCENDING
        else:
            self.sort_order = gtk.SORT_ASCENDING

        #tc.set_sort_order(self.sort_order) 
###############        
    def exit_program(self, widget, callback_data=None):
        gtk.main_quit()
#---------------------------------------------
if __name__ == "__main__":
    app = Application() 
    database_connection.commit()
    cursor.close()
    database_connection.close()
