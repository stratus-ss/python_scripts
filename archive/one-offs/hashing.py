def hash_rpms(hash_me):
    global hash_output
    try:
        import hashlib
        #Open the file for read-only and append the option to handle in case of being a binary file ('rb')
        file_to_hash = open(hash_me, 'rb')
        sha_hash = hashlib.sha1()
    except:
        import sha
        sha_hash = sha.new()
        file_to_hash = open(hash_me, 'rb')
        
        
    while True:
        #The data needs to be read in chunks for sha. SHA is more efficient than md5 as md5 can only handle 128 chunks
        data = file_to_hash.read(8192)
        #Loop through until there is no data left and then break the loop and calculate the final hash
        if not data:
            break
        sha_hash.update(data)
    hash_output = sha_hash.hexdigest()

def query_packages():
    import rpm
    #log the rpms
    list_of_rpms = "rpm.lst"
    old_stdout = sys.stdout
    sys.stdout = open(list_of_rpms, "w")
    transActions = rpm.TransactionSet()
    all_rpms = transActions.dbMatch()
    for individual_rpm in all_rpms:
        print "%s-%s-%s" % (individual_rpm['name'], individual_rpm['version'], individual_rpm['release'])
    sys.stdout = old_stdout
    hash_rpms(list_of_rpms)
