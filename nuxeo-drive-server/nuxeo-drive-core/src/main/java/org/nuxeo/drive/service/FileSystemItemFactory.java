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
package org.nuxeo.drive.service;

import org.nuxeo.drive.adapter.FileSystemItem;
import org.nuxeo.drive.service.impl.DefaultFileSystemItemFactory;
import org.nuxeo.ecm.core.api.ClientException;
import org.nuxeo.ecm.core.api.DocumentModel;

/**
 * Interface for the classes contributed to the {@code fileSystemItemFactory}
 * extension point of the {@link FileSystemItemAdapterService}.
 *
 * @author Antoine Taillefer
 * @see DefaultFileSystemItemFactory
 */
public interface FileSystemItemFactory {

    /**
     * Gets the {@link FileSystemItem} adapter for the given
     * {@link DocumentModel}.
     */
    FileSystemItem getFileSystemItem(DocumentModel doc) throws ClientException;

}