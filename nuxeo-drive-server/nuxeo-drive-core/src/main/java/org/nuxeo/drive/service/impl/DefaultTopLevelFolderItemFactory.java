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

import java.security.Principal;

import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.adapter.FolderItem;
import org.nuxeo.drive.adapter.impl.DefaultTopLevelFolderItem;
import org.nuxeo.drive.service.TopLevelFolderItemFactory;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.DocumentModel;

/**
 * Default implementation of a {@link TopLevelFolderItemFactory}.
 *
 * @author Antoine Taillefer
 */
public class DefaultTopLevelFolderItemFactory implements
        TopLevelFolderItemFactory {

    /**
     * Prevent from instantiating class as it should only be done by
     * {@link TopLevelFolderItemFactoryDescriptor#getFactory()}.
     */
    protected DefaultTopLevelFolderItemFactory() {
    }

    /*--------------------------- TopLevelFolderItemFactory ----------------------------*/
    @Override
    public FolderItem getTopLevelFolderItem(String userName)
            throws ClientException {
        return new DefaultTopLevelFolderItem(getName(), userName);
    }

    @Override
    public String getSyncRootParentFolderItemId(String userName)
            throws ClientException {
        return getTopLevelFolderItem(userName).getId();
    }

    /*--------------------------- FileSystemItemFactory --------------------------------*/
    @Override
    public void setName(String name) {
        throw new UnsupportedOperationException(
                "Cannot set the name of a TopLevelFolderItemFactory.");
    }

    @Override
    public String getName() {
        return getClass().getName();
    }

    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc)
            throws ClientException {
        throw new UnsupportedOperationException(
                "Cannot get the file system item for a given document from a TopLevelFolderItemFactory.");
    }

    @Override
    public FileSystemItem getFileSystemItem(DocumentModel doc, String parentId)
            throws ClientException {
        throw new UnsupportedOperationException(
                "Cannot get the file system item for a given document from a TopLevelFolderItemFactory.");
    }

    @Override
    public boolean canHandleFileSystemItemId(String id) {
        return (getName() + "/").equals(id);
    }

    @Override
    public boolean exists(String id, Principal principal)
            throws ClientException {
        if (!canHandleFileSystemItemId(id)) {
            throw new UnsupportedOperationException(
                    "Cannot check if a file system item with a given id exists for an id different than the top level folder item one from a TopLevelFolderItemFactory.");
        }
        return true;
    }

    @Override
    public FileSystemItem getFileSystemItemById(String id, Principal principal)
            throws ClientException {
        if (!canHandleFileSystemItemId(id)) {
            throw new UnsupportedOperationException(
                    "Cannot get the file system item for an id different than the top level folder item one from a TopLevelFolderItemFactory.");
        }
        return getTopLevelFolderItem(principal.getName());
    }

}
