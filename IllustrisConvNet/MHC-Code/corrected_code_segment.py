size_im=69
size_crop=207

data=fits.getdata(pathin+'training_kaggle.fit',1)
idcat=data['GalaxyID']
#sizev=data['petroR90_r_pix']
#avg_size=np.mean(sizev)
nparams=3
maxim=60000L; # 48000
D=np.zeros([maxim+1,3,size_im,size_im])
#D45=np.zeros([maxim+1,1,size_im,size_im])
Y=np.zeros([maxim+1,nparams])
idvec=np.zeros([maxim+1], dtype=np.long)
iteri=-1;
numim=0;
numim_init=numim
catalog=Table(data)

list=glob.glob('/grace/mhuertas/DES/ZOO/kaggle/*.jpg')

while iteri<maxim:
    try:
        #print(str(idvec[0]).zfill(6))
        #numgal=idcat[numim]
        file=list[numim]
        spl=file.split("/")
        filename=spl[6]
        numgal=filename.split(".")
        numgal=long(numgal[0])
        #size=sizev[numim]
        namegal=str(numgal)+".jpg"
        #hdulist = fits.open(pathin+namegal)
        scidata = misc.imread(namegal)
        f=np.nonzero(data['GalaxyID']==numgal);
        #size=data['petroR90_r_pix'][f]
        print('reading: '+pathin+namegal)
    except:
        print("Galaxy number %d is missing" % (numim))
        print(namegal)
        numim += 1
        continue
    #scidata1 = hdulist[0].data
    #lx,ly=scidata1.shape
    #if lx<113:
    #   numim+=1
    #    continue

    #scidata1 = hdulist[0].data
    lx,ly, lz=scidata.shape
    print "LX", lx
    if lx < 256 or ly<256:
        print "ENTRO"
        numim += 1
        continue
    #x = np.arange(lx) - (lx-1)/2.
    #y = np.arange(ly) - (ly-1)/2.
    #A, B = np.meshgrid(x, y)
    #d = np.sqrt(A**2 + B**2)
    #scidata1[np.transpose(d)>size*1.2]=0
    print lx,ly
    #fact=avg_size/size
    #print "FACT:", size, avg_size,fact
    #if fact==0:
    #    fact=1
    #scidata=scidata1[:,:,0]
    #for i in [0,1,2]:
    #max1=(scidata1[:,:,0]).max()
    #max2=(scidata1[:,:,1]).max()
    #max3=(scidata1[:,:,2]).max()
    #mv=[max1,max2,max3]
    #pos=np.argmax(mv)
    #scidata=scidata1[:,:,0]
    #scidata=zoom(scidata1[:,:,0], fact[0], order=3)
    print "SHAPE ", scidata.shape
    lx,ly, lz=scidata.shape
    #fact=1
    #if size < 10 or size > 50:
    #    numim+=1
    #    continue
    if lx<size_im:
        numim += 1
        continue
    scidata = extract_thumb(scidata,int(lx/2.0),int(ly/2.0),size_crop)
    scidata=zoom(scidata, [1/3.,1./3,1], order=3)
    #scidata1 = imresize(scidata1,(size_im,size_im,3))
    #hdulist.close()
    #scidata = (scidata1/1000.)
    #max_center=np.amax(scidata[size_im/2-4:size_im/2+4,size_im/2-4:size_im/2+4])
    #if max_center != scidata.max():
    #    numim+=1
    #    continue
    #scidata = scidata/max_center
    iteri=iteri+1
    scidata = np.transpose(scidata)
    print "MAX:", scidata.max()
    #scidata = np.expand_dims(scidata, axis=0)
    #scidata = np.expand_dims(scidata, axis=0)
    print scidata.shape
    D[iteri,:,:,:]=scidata
    #scidata45=scidata
    #scidata45 = extract_thumb(scidata45,int(lx/2.0),int(ly/2.0),size_im)
    #D45[iteri,:,:,:]=scidata45
    if iteri%10 ==0:
    #    hdu_w = fits.PrimaryHDU(scidata)
    #    stamp_name=pathin+"examples_stamps/"+str(numgal)+"_stamp_r.fits"
    #   hdu_w.writeto(stamp_name, clobber=True)
        misc.imsave(pathin+"examples/"+filename,np.transpose(scidata))

    Y[iteri,0]=data['Class1.1'][f]
    print Y[iteri,0], numgal
    Y[iteri,1]=data['Class1.2'][f]
    Y[iteri,2]=data['Class1.3'][f]
    idvec[iteri]=data['GalaxyID'][f]
    numim=numim+1
    print "ITER:",iteri
    Y = Y.squeeze()
