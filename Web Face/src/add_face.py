#importing libraries

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

import tensorflow as tf
import numpy as np
from scipy import misc
import align.detect_face
import facenet
import cv2
import os
import time
import math


#(tf_session, tf_graph, image_dir, classes_numpy, labels_numpy, embed_numpy)
def main(sess, graph, image_dir, class_names, labels, embeds):
  
    	batch_size=100
    	image_margin=44
    	image_size=160
    	min_nr_of_images_per_class=1
    
    	with graph.as_default():
      
        	with sess.as_default():
            
            		st = time.time()
            		dataset = facenet.get_dataset(image_dir)
            
			#removing faces that already exists            
			print('Removing already added faces')
            		dataset = [x for x in dataset if not x.name.replace('_', ' ') in class_names]
            
			# Check that there are at least one training image per class
            		for cls in dataset:
                		assert len(cls.image_paths)>0, 'There must be at least one image for each class in the dataset'
            
			#if no new faces to add then teminate
            		if not dataset:
                		print('no new faces to be added... terminating')
                		return False             
        
            		paths, new_labels = facenet.get_image_paths_and_labels(dataset)
 			print('Number of classes: %d' % len(dataset))
            		print('Number of images: %d' % len(paths))
            
            
            		# Get input and output tensors
            		images_placeholder = tf.get_default_graph().get_tensor_by_name("input:0")
            		embeddings = tf.get_default_graph().get_tensor_by_name("embeddings:0")
            		phase_train_placeholder = tf.get_default_graph().get_tensor_by_name("phase_train:0")
            		embedding_size = embeddings.get_shape()[1]
            
           		# Run forward pass to calculate embeddings
            		print('Calculating features for images')
            		nrof_images = len(paths)
            		nrof_batches_per_epoch = int(math.ceil(1.0*nrof_images / batch_size))
            		new_emb_array = np.zeros((nrof_images, embedding_size))
            		for i in range(nrof_batches_per_epoch):
                		start_index = i*batch_size
                		end_index = min((i+1)*batch_size, nrof_images)
                		paths_batch = paths[start_index:end_index]
                		images = load_and_align_data(paths_batch, 160, 44, 0.9)
                		feed_dict = { images_placeholder:images, phase_train_placeholder:False }
                		new_emb_array[start_index:end_index,:] = sess.run(embeddings, feed_dict=feed_dict)
                
            
            		# Adding embeds and names in database
            		new_class_names = [ cls.name.replace('_', ' ') for cls in dataset]
            		new_labels = np.array(new_labels)
            		new_labels = new_labels + class_names.size
            
            		class_names=np.append(class_names,new_class_names)
            		embeds=np.concatenate((embeds,new_emb_array), axis=0)
            		labels=np.append(labels,new_labels)
            
            		np.save('embed',embeds)
            		np.save('labels',labels)
            		np.save('classnames',class_names)
            		
    			print('Elapsed Time = {}'.format(time.time() - st)) 
	
	return class_names, labels, embeds

def load_and_align_data(image_paths, image_size, margin, gpu_memory_fraction):

    	minsize = 20 # minimum size of face
    	threshold = [ 0.6, 0.7, 0.7 ]  # three steps's threshold
    	factor = 0.709 # scale factor
    
    	print('Creating networks and loading parameters')
    	with tf.Graph().as_default():
        	gpu_options = tf.GPUOptions(per_process_gpu_memory_fraction=gpu_memory_fraction)
        	sess = tf.Session(config=tf.ConfigProto(gpu_options=gpu_options, log_device_placement=False))
        	with sess.as_default():
            		pnet, rnet, onet = align.detect_face.create_mtcnn(sess, None)
  
    	nrof_samples = len(image_paths)
    	img_list = [None] * nrof_samples
    	for i in range(nrof_samples):
        	img = misc.imread(os.path.expanduser(image_paths[i]))
		img_size = np.asarray(img.shape)[0:2]
        	bounding_boxes, _ = align.detect_face.detect_face(img, minsize, pnet, rnet, onet, threshold, factor)
        	det = np.squeeze(bounding_boxes[0,0:4])
        	bb = np.zeros(4, dtype=np.int32)
        	bb[0] = np.maximum(det[0]-margin/2, 0)
        	bb[1] = np.maximum(det[1]-margin/2, 0)
        	bb[2] = np.minimum(det[2]+margin/2, img_size[1])
        	bb[3] = np.minimum(det[3]+margin/2, img_size[0])
        	cropped = img[bb[1]:bb[3],bb[0]:bb[2],:]
        	aligned = misc.imresize(cropped, (image_size, image_size), interp='bilinear')
        	prewhitened = facenet.prewhiten(aligned)
        	img_list[i] = prewhitened
		
    	images = np.stack(img_list)
    	return images
            
if __name__ == '__main__':
    main(sess, graph, image_dir, class_names, labels, embeds)
