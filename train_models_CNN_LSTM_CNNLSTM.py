'''
Model architectures are inspired from the (conference) paper:

Kim, Myungjong & Cao, Beiming & An, Kwanghoon & Wang, Jun. (2018). Dysarthric Speech Recognition Using Convolutional LSTM Neural Network. 10.21437/interspeech.2018-2250. 

'''

import os
import time
import datetime
import numpy as np
import matplotlib.pyplot as plt
import csv

# for building and training models
import keras
#from keras.models import Sequential
#from keras.layers import Dense, Conv2D, Flatten, LSTM, MaxPooling2D, Dropout, TimeDistributed, ConvLSTM2D
from keras.callbacks import EarlyStopping,ReduceLROnPlateau,CSVLogger,ModelCheckpoint

from model_scripts.generator_speech_CNN_LSTM import Generator
import model_scripts.build_model as build


#to keep saved files unique
#include their names with a timestamp
def get_date():
    time = datetime.datetime.now()
    time_str = "{}d{}h{}m{}s".format(time.day,time.hour,time.minute,time.second)
    return(time_str)

def main(model_type,epochs,optimizer,sparse_targets,patience=None):
    if patience is None:
        patience = 10
    
    #####################################################################
    ######################## HOUSE KEEPING ##############################
    
    start = time.time()
    time_stamp = get_date()
    
    print("\n\nWhich folder contains the train, validation, and test datasets you would like to train this model on?\n")
    project_head_folder=input()
    
    head_folder_beg = "./ml_speech_projects/"
    head_folder_curr_project = head_folder_beg+project_head_folder
    #create folders to store models, logs, and graphs
    graphs_folder = head_folder_curr_project+"/graphs"
    models_folder =  head_folder_curr_project+"/models"
    model_log_folder = head_folder_curr_project+"/model_logs"
    
    for folder in [graphs_folder,models_folder,model_log_folder]:
        if not os.path.exists(folder):
            os.makedirs(folder)
    
    #make model name unique with timestamp
    modelname = "{}_speech_commands_{}".format(model_type.upper(),time_stamp)
    
    
    #collect variables stored during feature extraction
    load_feature_settings_file = head_folder_curr_project+"/features_log.csv".format(project_head_folder)
    with open(load_feature_settings_file, mode='r') as infile:
        reader = csv.reader(infile)            
        feats_dict = {rows[0]:rows[1] for rows in reader}
    
    num_labels = int(feats_dict['num classes'])
    num_features = int(feats_dict['num total features'])
    timesteps = int(feats_dict['timesteps'])
    context_window = int(feats_dict['context window'])
    
    print("\nInfo about training data:\n".upper())
    for key, item in feats_dict.items():
        print(key," : ",item)
    
    frame_width = context_window*2+1
    color_scale = 1 
    #####################################################################
    ######################### BUILD MODEL  ##############################
    

    
    #based on number of labels, set model settings:
    loss_type, activation_output = build.assign_model_settings(num_labels,sparse_targets)

    #build the model architecture:
    #read up on what they do and feel free to adjust!
    #For the LSTM:
    lstm_cells = 40
    #For the CNN:
    feature_map_filters = 30
    kernel_size = (4,8)
    #maxpooling
    pool_size = (3,3)
    #hidden dense layer
    dense_hidden_units = 60
    
    model = build.buildmodel(model_type,num_labels,frame_width,timesteps,num_features,color_scale,lstm_cells,feature_map_filters,kernel_size,pool_size,dense_hidden_units,activation_output)
    
    #see what the model architecture looks like:
    print(model.summary())
    model.compile(optimizer=optimizer,loss=loss_type,metrics=['accuracy'])

    
    ######################################################################
    ###################### MORE HOUSEKEEPING!  ###########################
    
    #set up "callbacks" which help you keep track of what goes on during training
    #also saves the best version of the model and stops training if learning doesn't improve 
    early_stopping_callback = EarlyStopping(monitor='val_loss', patience=patience)
    csv_logging = CSVLogger(filename='{}/{}_log.csv'.format(model_log_folder,modelname))
    checkpoint_callback = ModelCheckpoint('{}/checkpoint_'.format(models_folder)+modelname+'.h5', monitor='val_loss', verbose=1, save_best_only=True, mode='min')


    #####################################################################
    ################ LOAD TRAINING AND VALIDATION DATA  #################
    filename_train = "ml_speech_projects/{}/data_train/train_features.npy".format(project_head_folder)
    train_data = np.load(filename_train)
    
    filename_val = "ml_speech_projects/{}/data_val/val_features.npy".format(project_head_folder)
    val_data = np.load(filename_val)

    #load these into their generators
    train_generator = Generator(model_type,train_data,timesteps,frame_width)
    val_generator = Generator(model_type,val_data,timesteps,frame_width)


    #####################################################################
    #################### TRAIN AND TEST THE MODEL #######################
    
    start_training = time.time()
    #train the model and keep the accuracy and loss stored in the variable 'history'
    #helpful in logging/plotting how training and validation goes
    history = model.fit_generator(
            train_generator.generator(),
            steps_per_epoch = train_data.shape[0]/(timesteps*frame_width),
            epochs = epochs,
            callbacks=[early_stopping_callback, checkpoint_callback],
            validation_data = val_generator.generator(), 
            validation_steps = val_data.shape[0]/(timesteps*frame_width)
            )
    end_training = time.time()
    
    print("\nNow testing the model..")
    #now to test the model on brandnew data!
    filename_test = "ml_speech_projects/{}/data_test/test_features.npy".format(project_head_folder)
    test_data = np.load(filename_test)
    test_generator = Generator(model_type,test_data,timesteps,frame_width)
    score = model.evaluate_generator(test_generator.generator(), test_data.shape[0]/(timesteps*frame_width))
    loss = round(score[0],2)
    acc = round(score[1]*100,3)

    msg="Model Accuracy on test data: {}%\nModel Loss on test data: {}".format(acc,loss)
    print(msg)
    
    print("Saving model..")
    model.save('{}/'.format(models_folder)+modelname+'.h5')
    print('Done!')
    print("\nModel saved as:\n{}.h5".format(models_folder+"/"+modelname))
    
    #####################################################################
    ####### TRY AND SEE WHAT THE HECK WAS GOING ON WHILE TRAINING #######

    print("Now saving history and plots")
    plt.plot(history.history['loss'])
    plt.plot(history.history['val_loss'])
    plt.title("train vs validation loss")
    plt.ylabel("loss")
    plt.xlabel("epoch")
    plt.legend(["train","validation"], loc="upper right")
    plt.savefig("{}/{}_LOSS.png".format(graphs_folder,modelname))

    plt.clf()
    plt.plot(history.history['acc'])
    plt.plot(history.history['val_acc'])
    plt.title("train vs validation accuracy")
    plt.ylabel("accuracy")
    plt.xlabel("epoch")
    plt.legend(["train","validation"], loc="upper right")
    plt.savefig("{}/{}_ACCURACY.png".format(graphs_folder,modelname))
    
    end = time.time()
    duration_total = round((end-start)/60,3)
    duration_training = round((end_training-start_training)/60,3)
    print("\nTotal duration = {}\nTraining duration = {}\n".format(duration_total,duration_training))
    
    
    #####################################################################
    ########## KEEP TRACK OF SETTINGS AND THE LOSS/ACCURACY #############
    

    #document settings used in model
    parameters = {}
    parameters["model type"] = model_type.lower()
    parameters["epochs"] = epochs
    if "lstm" in model_type.lower():
        parameters["num lstm cells"] = lstm_cells
    if "cnn" in model_type.lower():
        parameters["cnn feature maps"] = feature_map_filters
        parameters["cnn kernel size"] = kernel_size
        parameters["cnn maxpooling pool size"] = pool_size
        if "cnn" == model_type.lower():
            parameters["cnn dense hidden units"] = dense_hidden_units
    parameters["optimizer"] = optimizer
    parameters["num training data"] = len(train_data)

    #just to keep track and know for sure how many classes got presented during training and validation
    for key, value in train_generator.dict_classes_encountered.items():
        parameters["label "+str(key)+" representation in training"] = value
    for key, value in val_generator.dict_classes_encountered.items():
        parameters["label "+str(key)+" representation in validation"] = value
    parameters["loss type"] = loss_type
    parameters["activation output"] = activation_output
    parameters["test acc"] = acc
    parameters["test loss"] = loss
    #save in csv file
    with open('{}/{}.csv'.format(model_log_folder,modelname),'w',newline='') as f:
        w = csv.writer(f)
        w.writerows(parameters.items())
    
    return True



if __name__ == "__main__":
    
    
    model_type = "cnnlstm" # cnn, lstm, cnnlstm
    epochs = 100
    optimizer = 'adam' # 'adam' 'sgd'
    sparse_targets = True
    patience = 5 
    
    
    main(model_type,epochs,optimizer,sparse_targets,patience)
