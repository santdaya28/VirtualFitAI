import React from 'react';
import { Shirt, Home } from 'lucide-react';
import Container from '../components/Container';
import Button from '../components/Button';

export default function NotFoundPage() {
  return (
    <div className="py-20 flex-1 flex items-center justify-center">
      <Container size="narrow" className="text-center space-y-6">
        <div className="w-16 h-16 rounded-2xl bg-indigo-50 text-indigo-600 flex items-center justify-center mx-auto shadow-xs">
          <Shirt className="w-8 h-8" />
        </div>
        <div className="space-y-2">
          <span className="text-xs font-bold text-indigo-600 tracking-widest uppercase">
            404 Error
          </span>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900">
            Page Not Found
          </h1>
          <p className="text-sm text-slate-600 max-w-sm mx-auto">
            The page you are looking for does not exist in the VirtualFit AI platform.
          </p>
        </div>
        <div className="flex items-center justify-center gap-3">
          <Button
            to="/"
            variant="primary"
            size="md"
            leftIcon={Home}
          >
            Back to Home
          </Button>
          <Button
            to="/try-on"
            variant="outline"
            size="md"
          >
            Try-On Studio
          </Button>
        </div>
      </Container>
    </div>
  );
}
