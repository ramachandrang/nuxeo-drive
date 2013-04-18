/*
 * (C) Copyright 2012 Nuxeo SA (http://nuxeo.com/) and contributors.
 *
 * All rights reserved. This program and the accompanying materials
 * are made available under the terms of the GNU Lesser General Public License
 * (LGPL) version 2.1 which accompanies this distribution, and is available at
 * http://www.gnu.org/licenses/lgpl.html
 *
 * This library is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the GNU
 * Lesser General Public License for more details.
 *
 * Contributors:
 *     Antoine Taillefer <ataillefer@nuxeo.com>
 */
package org.nuxeo.drive.service.impl;

import java.util.ArrayList;
import java.util.Iterator;
import java.util.List;
import java.util.Map;

import org.apache.commons.lang.StringUtils;
import org.apache.commons.logging.Log;
import org.apache.commons.logging.LogFactory;
import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.adapter.FolderItem;
import org.nuxeo.drive.adapter.RootlessItemException;
import org.nuxeo.drive.service.FileSystemItemAdapterService;
import org.nuxeo.drive.service.FileSystemItemFactory;
import org.nuxeo.drive.service.TopLevelFolderItemFactory;
import org.nuxeo.drive.service.VirtualFolderItemFactory;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.DocumentModel;
import org.nuxeo.runtime.model.ComponentContext;
import org.nuxeo.runtime.model.ComponentInstance;
import org.nuxeo.runtime.model.DefaultComponent;

/**
 * Default implementation of the {@link FileSystemItemAdapterService}.
 *
 * @author Antoine Taillefer
 */
public class FileSystemItemAdapterServiceImpl extends DefaultComponent
        implements FileSystemItemAdapterService {

    private static final Log log = LogFactory.getLog(FileSystemItemAdapterServiceImpl.class);

    public static final String FILE_SYSTEM_ITEM_FACTORY_EP = "fileSystemItemFactory";

    public static final String TOP_LEVEL_FOLDER_ITEM_FACTORY_EP = "topLevelFolderItemFactory";

    protected FileSystemItemFactoryRegistry fileSystemItemFactoryRegistry;

    protected TopLevelFolderItemFactoryRegistry topLevelFolderItemFactoryRegistry;

    protected List<FileSystemItemFactoryWrapper> fileSystemItemFactories;

    /*------------------------ DefaultComponent -----------------------------*/
    @Override
    public void registerContribution(Object contribution,
            String extensionPoint, ComponentInstance contributor)
            throws Exception {
        if (FILE_SYSTEM_ITEM_FACTORY_EP.equals(extensionPoint)) {
            fileSystemItemFactoryRegistry.addContribution((FileSystemItemFactoryDescriptor) contribution);
        } else if (TOP_LEVEL_FOLDER_ITEM_FACTORY_EP.equals(extensionPoint)) {
            topLevelFolderItemFactoryRegistry.addContribution((TopLevelFolderItemFactoryDescriptor) contribution);
        } else {
            log.error("Unknown extension point " + extensionPoint);
        }
    }

    @Override
    public void unregisterContribution(Object contribution,
            String extensionPoint, ComponentInstance contributor)
            throws Exception {
        if (FILE_SYSTEM_ITEM_FACTORY_EP.equals(extensionPoint)) {
            fileSystemItemFactoryRegistry.removeContribution((FileSystemItemFactoryDescriptor) contribution);
        } else if (TOP_LEVEL_FOLDER_ITEM_FACTORY_EP.equals(extensionPoint)) {
            topLevelFolderItemFactoryRegistry.removeContribution((TopLevelFolderItemFactoryDescriptor) contribution);
        } else {
            log.error("Unknown extension point " + extensionPoint);
        }
    }

    @Override
    public void activate(ComponentContext context) {
        fileSystemItemFactoryRegistry = new FileSystemItemFactoryRegistry();
        topLevelFolderItemFactoryRegistry = new TopLevelFolderItemFactoryRegistry();
        fileSystemItemFactories = new ArrayList<FileSystemItemFactoryWrapper>();
    }

    @Override
    public void deactivate(ComponentContext context) throws Exception {
        super.deactivate(context);
        fileSystemItemFactoryRegistry = null;
        topLevelFolderItemFactoryRegistry = null;
        fileSystemItemFactories = null;
    }

    /**
     * Sorts the contributed factories according to their order.
     */
    @Override
    public void applicationStarted(ComponentContext context) throws Exception {
        sortFileSystemItemFactories();
    }

    /*------------------------ FileSystemItemAdapterService -----------------------*/
    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc)
            throws ClientException {
        return getFileSystemItem(doc, false, null, false);
    }

    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc,
            boolean includeDeleted) throws ClientException {
        return getFileSystemItem(doc, false, null, includeDeleted);
    }

    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc,
            FolderItem parentItem) throws ClientException {
        return getFileSystemItem(doc, true, parentItem, false);
    }

    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc,
            FolderItem parentItem, boolean includeDeleted)
            throws ClientException {
        return getFileSystemItem(doc, true, parentItem, includeDeleted);
    }

    /**
     * Iterates on the ordered contributed file system item factories until if
     * finds one that can handle the given {@link FileSystemItem} id.
     */
    @Override
    public FileSystemItemFactory getFileSystemItemFactoryForId(String id)
            throws ClientException {
        Iterator<FileSystemItemFactoryWrapper> factoriesIt = fileSystemItemFactories.iterator();
        while (factoriesIt.hasNext()) {
            FileSystemItemFactoryWrapper factoryWrapper = factoriesIt.next();
            FileSystemItemFactory factory = factoryWrapper.getFactory();
            if (factory.canHandleFileSystemItemId(id)) {
                return factory;
            }
        }
        // No fileSystemItemFactory found, try the topLevelFolderItemFactory
        TopLevelFolderItemFactory topLevelFolderItemFactory = getTopLevelFolderItemFactory();
        if (topLevelFolderItemFactory.canHandleFileSystemItemId(id)) {
            return topLevelFolderItemFactory;
        }
        throw new ClientException(
                String.format(
                        "No fileSystemItemFactory found for FileSystemItem with id %s. Please check the contributions to the following extension point: <extension target=\"org.nuxeo.drive.service.FileSystemItemAdapterService\" point=\"fileSystemItemFactory\"> and make sure there is at least one defining a FileSystemItemFactory class for which the #canHandleFileSystemItemId(String id) method returns true.",
                        id));
    }

    @Override
    public TopLevelFolderItemFactory getTopLevelFolderItemFactory()
            throws ClientException {
        if (topLevelFolderItemFactoryRegistry.factory == null) {
            throw new ClientException(
                    "Found no topLevelFolderItemFactory. Please check there is a contribution to the following extension point: <extension target=\"org.nuxeo.drive.service.FileSystemItemAdapterService\" point=\"topLevelFolderItemFactory\">.");
        }
        return topLevelFolderItemFactoryRegistry.factory;
    }

    @Override
    public VirtualFolderItemFactory getVirtualFolderItemFactory(
            String factoryName) throws ClientException {
        FileSystemItemFactory factory = getFileSystemItemFactory(factoryName);
        if (factory == null) {
            throw new ClientException(
                    String.format(
                            "No factory named %s. Please check the contributions to the following extension point: <extension target=\"org.nuxeo.drive.service.FileSystemItemAdapterService\" point=\"fileSystemItemFactory\">.",
                            factoryName));
        }
        if (!(factory instanceof VirtualFolderItemFactory)) {
            throw new ClientException(
                    String.format(
                            "Factory class %s for factory %s is not a VirtualFolderItemFactory.",
                            factory.getClass().getName(), factory.getName()));
        }
        return (VirtualFolderItemFactory) factory;
    }

    /*------------------------- For test purpose ----------------------------------*/
    public Map<String, FileSystemItemFactoryDescriptor> getFileSystemItemFactoryDescriptors() {
        return fileSystemItemFactoryRegistry.factoryDescriptors;
    }

    public List<FileSystemItemFactoryWrapper> getFileSystemItemFactories() {
        return fileSystemItemFactories;
    }

    public FileSystemItemFactory getFileSystemItemFactory(String name) {
        for (FileSystemItemFactoryWrapper factoryWrapper : fileSystemItemFactories) {
            FileSystemItemFactory factory = factoryWrapper.getFactory();
            if (name.equals(factory.getName())) {
                return factory;
            }
        }
        log.debug(String.format(
                "No fileSystemItemFactory named %s, returning null.", name));
        return null;
    }

    /*--------------------------- Protected ---------------------------------------*/
    protected void sortFileSystemItemFactories() throws Exception {
        fileSystemItemFactories = fileSystemItemFactoryRegistry.getOrderedFactories();
    }

    /**
     * Tries to adapt the given document as the top level {@link FolderItem}. If
     * it doesn't match, iterates on the ordered contributed file system item
     * factories until it finds one that matches and retrieves a non null
     * {@link FileSystemItem} for the given document. A file system item factory
     * matches if:
     * <ul>
     * <li>It is not bound to any docType nor facet (this is the case for the
     * default factory contribution {@code defaultFileSystemItemFactory} bound
     * to {@link DefaultFileSystemItemFactory})</li>
     * <li>It is bound to a docType that matches the given doc's type</li>
     * <li>It is bound to a facet that matches one of the given doc's facets</li>
     * </ul>
     */
    protected FileSystemItem getFileSystemItem(DocumentModel doc,
            boolean forceParentItem, FolderItem parentItem,
            boolean includeDeleted) throws ClientException {

        FileSystemItem fileSystemItem = null;

        // Try the topLevelFolderItemFactory
        TopLevelFolderItemFactory topLevelFolderItemFactory = getTopLevelFolderItemFactory();
        if (forceParentItem) {
            fileSystemItem = topLevelFolderItemFactory.getFileSystemItem(doc,
                    parentItem, includeDeleted);
        } else {
            fileSystemItem = topLevelFolderItemFactory.getFileSystemItem(doc,
                    includeDeleted);
        }
        if (fileSystemItem != null) {
            return fileSystemItem;
        } else {
            log.debug(String.format(
                    "The topLevelFolderItemFactory is not able to adapt document %s as a FileSystemItem => trying fileSystemItemFactories.",
                    doc.getId()));
        }

        // Try the fileSystemItemFactories
        FileSystemItemFactoryWrapper matchingFactory = null;
        Iterator<FileSystemItemFactoryWrapper> factoriesIt = fileSystemItemFactories.iterator();
        while (factoriesIt.hasNext()) {
            FileSystemItemFactoryWrapper factory = factoriesIt.next();
            if (generalFactoryMatches(factory)
                    || docTypeFactoryMatches(factory, doc)
                    || facetFactoryMatches(factory, doc)) {
                matchingFactory = factory;
                try {
                    if (forceParentItem) {
                        fileSystemItem = factory.getFactory().getFileSystemItem(
                                doc, parentItem, includeDeleted);
                    } else {
                        fileSystemItem = factory.getFactory().getFileSystemItem(
                                doc, includeDeleted);
                    }
                } catch (RootlessItemException e) {
                    // Give more information in the exception message on the
                    // document whose adaption failed to recursively find the
                    // top level item.
                    throw new RootlessItemException(String.format(
                            "Cannot find path to registered top"
                                    + " level when adapting document "
                                    + " '%s' (path: %s) with factory %s",
                            doc.getTitle(), doc.getPathAsString(),
                            factory.getFactory().getName()), e);
                }
                if (fileSystemItem != null) {
                    log.debug(String.format(
                            "Adapted document '%s' (path: %s) to item with path %s with factory %s",
                            doc.getTitle(), doc.getPathAsString(),
                            fileSystemItem.getPath(),
                            factory.getFactory().getName()));
                    return fileSystemItem;
                }
            }
        }

        if (matchingFactory == null) {
            log.debug(String.format(
                    "None of the fileSystemItemFactories matches document %s => returning null. Please check the contributions to the following extension point: <extension target=\"org.nuxeo.drive.service.FileSystemItemAdapterService\" point=\"fileSystemItemFactory\">.",
                    doc.getId()));
        } else {
            log.debug(String.format(
                    "None of the fileSystemItemFactories matching document %s were able to adapt this document as a FileSystemItem => returning null.",
                    doc.getId()));
        }
        return fileSystemItem;
    }

    protected boolean generalFactoryMatches(FileSystemItemFactoryWrapper factory) {
        return StringUtils.isEmpty(factory.getDocType())
                && StringUtils.isEmpty(factory.getFacet());
    }

    protected boolean docTypeFactoryMatches(
            FileSystemItemFactoryWrapper factory, DocumentModel doc) {
        return !StringUtils.isEmpty(factory.getDocType())
                && factory.getDocType().equals(doc.getType());
    }

    protected boolean facetFactoryMatches(FileSystemItemFactoryWrapper factory,
            DocumentModel doc) throws ClientException {
        if (!StringUtils.isEmpty(factory.getFacet())) {
            for (String docFacet : doc.getFacets()) {
                if (factory.getFacet().equals(docFacet)) {
                    // Handle synchronization root case
                    if (NuxeoDriveManagerImpl.NUXEO_DRIVE_FACET.equals(docFacet)) {
                        return syncRootFactoryMatches(doc);
                    } else {
                        return true;
                    }
                }
            }
        }
        return false;
    }

    @SuppressWarnings("unchecked")
    protected boolean syncRootFactoryMatches(DocumentModel doc)
            throws ClientException {
        String userName = doc.getCoreSession().getPrincipal().getName();
        List<Map<String, Object>> subscriptions = (List<Map<String, Object>>) doc.getPropertyValue(NuxeoDriveManagerImpl.DRIVE_SUBSCRIPTIONS_PROPERTY);
        for (Map<String, Object> subscription : subscriptions) {
            if (userName.equals(subscription.get("username"))) {
                if (Boolean.TRUE.equals(subscription.get("enabled"))) {
                    return true;
                }
            }
        }
        return false;
    }

}
